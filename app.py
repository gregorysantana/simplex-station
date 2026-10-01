"""Estación de entrada de paquetes (Simplex) — Flask local.

Cámara (OpenCV) + código de barras (zxing) + IA/OCR (nube u offline) + balanza PS60 + impresión,
empujando a Simplex por token de estación. UI en el navegador: http://localhost:PORT
"""
import os, threading, time
from flask import Flask, Response, request, jsonify, render_template
from dotenv import load_dotenv

import vision, scale as scale_mod, printer as printer_mod
from simplex import Simplex

load_dotenv()
CFG = {k: os.getenv(k, '') for k in (
    'SIMPLEX_URL', 'STATION_TOKEN', 'CAMERA_INDEX', 'AI_MODE',
    'GEMINI_API_KEY', 'GEMINI_MODEL', 'OPENAI_API_KEY', 'OPENAI_MODEL',
    'ANTHROPIC_API_KEY', 'ANTHROPIC_MODEL', 'SCALE_VENDOR_ID', 'SCALE_PRODUCT_ID',
    'LABEL_PRINTER', 'PORT')}

app = Flask(__name__)
sx = Simplex(CFG['SIMPLEX_URL'] or 'https://simplex.do', CFG['STATION_TOKEN'])


class Camera:
    """Captura en hilo; expone el último frame para MJPEG y /capture."""
    def __init__(self, index=0):
        self.index = index
        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.run = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        import cv2
        while self.run:
            if self.cap is None:
                self.cap = cv2.VideoCapture(self.index)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            ok, fr = self.cap.read()
            if ok:
                with self.lock:
                    self.frame = fr
            else:
                time.sleep(0.1)
            time.sleep(0.03)

    def get(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()


cam = Camera(int(CFG['CAMERA_INDEX'] or 0))


def mjpeg():
    import cv2
    while True:
        fr = cam.get()
        if fr is not None:
            ok, buf = cv2.imencode('.jpg', fr)
            if ok:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
        time.sleep(0.05)


@app.route('/')
def index():
    return render_template('index.html', cfg={'ai_mode': CFG['AI_MODE'] or 'offline'})


@app.route('/video')
def video():
    return Response(mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/capture', methods=['POST'])
def capture():
    """Lee el frame actual: barcode (tracking) + IA/OCR (nombre/casillero/contenido)."""
    fr = cam.get()
    if fr is None:
        return jsonify(ok=False, message='sin cámara')
    tracking = vision.decode_barcode(fr)
    label = vision.read_label(fr, CFG['AI_MODE'] or 'offline', CFG)
    out = {
        'ok': True,
        'tracking': tracking or '',
        'recipient_name': label.get('recipient_name', ''),
        'casillero': label.get('casillero', ''),
        'content': label.get('content', ''),
        'supplier': label.get('supplier', ''),
        'ai_error': label.get('_error', ''),
    }
    # Match de cliente por casillero/nombre.
    q = out['casillero'] or out['recipient_name']
    if q:
        r = sx.client_search(q)
        out['client_matches'] = (r or {}).get('data', [])
    return jsonify(out)


@app.route('/api/weight')
def weight():
    lb, stable, msg = scale_mod.read_weight_lb(CFG['SCALE_VENDOR_ID'] or None, CFG['SCALE_PRODUCT_ID'] or None)
    return jsonify(ok=lb is not None, weight_lb=lb, stable=stable, message=msg)


@app.route('/api/clients/search')
def clients_search():
    return jsonify(sx.client_search(request.args.get('q', '')))


@app.route('/api/containers')
def containers():
    return jsonify(sx.containers())


@app.route('/api/containers/create', methods=['POST'])
def container_create():
    return jsonify(sx.container_create((request.json or {}).get('code', '')))


@app.route('/api/pending')
def pending():
    return jsonify(sx.intake_pending())


@app.route('/api/submit', methods=['POST'])
def submit():
    """Crea el paquete en Simplex y (opcional) imprime etiqueta."""
    data = request.json or {}
    payload = {
        'client_id': data.get('client_id'),
        'tracking_number': data.get('tracking_number', ''),
        'auto_tracking': 1 if not data.get('tracking_number') else 0,
        'carrier': data.get('carrier', ''),
        'content': data.get('content', ''),
        'supplier': data.get('supplier', ''),
        'packaging_type_id': data.get('packaging_type_id', 0),
        'fob': data.get('fob', 0),
        'weight_lb': data.get('weight_lb', 0),
        'container_id': data.get('container_id', 0),
    }
    r = sx.package_create(payload)
    if r.get('success') and data.get('print') and r.get('label'):
        ok, msg = printer_mod.print_label({**r['label'], 'weight_lb': payload['weight_lb']}, CFG['LABEL_PRINTER'])
        r['print_ok'] = ok
        r['print_msg'] = msg
    return jsonify(r)


if __name__ == '__main__':
    port = int(CFG['PORT'] or 8777)
    print(f"Estación Simplex en http://localhost:{port}  (AI_MODE={CFG['AI_MODE']})")
    app.run(host='127.0.0.1', port=port, threaded=True)
