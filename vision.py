"""Lectura de etiqueta: código de barras (tracking) + IA/OCR para nombre, casillero, contenido.

- El TRACKING siempre sale del código de barras (1D), nunca del QR ni OCR.
- Los campos de texto (nombre/casillero/contenido/suplidor) salen de IA en la nube
  (Gemini/OpenAI/Claude) devolviendo JSON, o de OCR offline (PaddleOCR) como respaldo.
"""
import os, io, json, base64, re

# ---- Código de barras (zxing-cpp) ----
def _good(txt, fmt=''):
    txt = (txt or '').strip()
    if not txt or len(txt) < 8:
        return None
    if 'QR' in (fmt or '').upper():
        return None
    return txt

def decode_barcode(bgr_image):
    """Devuelve el mejor tracking 1D del frame (prueba rotaciones). None si no hay.
    Usa zxing-cpp si está disponible; si no, el detector de barcode de OpenCV."""
    import cv2
    rots = (None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_180)

    # 1) zxing-cpp (si está instalado)
    try:
        import zxingcpp
        for rot in rots:
            img = bgr_image if rot is None else cv2.rotate(bgr_image, rot)
            try:
                for r in zxingcpp.read_barcodes(img):
                    t = _good(r.text, str(getattr(r, 'format', '')))
                    if t:
                        return t
            except Exception:
                pass
    except Exception:
        pass

    # 2) OpenCV barcode (opencv-contrib)
    try:
        det = cv2.barcode.BarcodeDetector()
        for rot in rots:
            img = bgr_image if rot is None else cv2.rotate(bgr_image, rot)
            try:
                res = det.detectAndDecode(img)
            except Exception:
                res = None
            if not res:
                continue
            # API varía: (ok, infos, types, pts) o (infos, types, pts)
            infos = None
            if isinstance(res, tuple):
                if len(res) == 4:
                    infos = res[1]
                elif len(res) == 3:
                    infos = res[0]
            for s in (infos or []):
                t = _good(s)
                if t:
                    return t
    except Exception:
        pass
    return None


# ---- IA en la nube: devuelve dict estructurado ----
_PROMPT = (
    "Eres un asistente que lee etiquetas de paquetes de un courier. "
    "Devuelve SOLO un JSON con estas claves (usa cadenas vacías si no aparece): "
    '{"recipient_name":"", "casillero":"", "content":"", "supplier":""}. '
    "El casillero es un código de membresía tipo H-000025 o similar (NO es el ZIP ni el teléfono). "
    "El nombre es el destinatario (consignatario). No inventes datos."
)

def _img_to_jpeg_b64(bgr_image):
    import cv2
    ok, buf = cv2.imencode('.jpg', bgr_image)
    return base64.b64encode(buf.tobytes()).decode('ascii')

def _parse_json(text):
    m = re.search(r'\{.*\}', text or '', re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}

def read_label_ai(bgr_image, mode, keys):
    """mode: gemini|openai|claude. keys: dict con las API keys/modelos."""
    b64 = _img_to_jpeg_b64(bgr_image)
    try:
        if mode == 'gemini':
            import google.generativeai as genai
            genai.configure(api_key=keys['GEMINI_API_KEY'])
            model = genai.GenerativeModel(keys.get('GEMINI_MODEL') or 'gemini-2.5-flash')
            resp = model.generate_content([_PROMPT, {'mime_type': 'image/jpeg', 'data': base64.b64decode(b64)}])
            return _parse_json(resp.text)
        if mode == 'openai':
            from openai import OpenAI
            cli = OpenAI(api_key=keys['OPENAI_API_KEY'])
            resp = cli.chat.completions.create(
                model=keys.get('OPENAI_MODEL') or 'gpt-4.1',
                messages=[{'role': 'user', 'content': [
                    {'type': 'text', 'text': _PROMPT},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}},
                ]}])
            return _parse_json(resp.choices[0].message.content)
        if mode == 'claude':
            import anthropic
            cli = anthropic.Anthropic(api_key=keys['ANTHROPIC_API_KEY'])
            resp = cli.messages.create(
                model=keys.get('ANTHROPIC_MODEL') or 'claude-sonnet-5', max_tokens=300,
                messages=[{'role': 'user', 'content': [
                    {'type': 'text', 'text': _PROMPT},
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}},
                ]}])
            return _parse_json(resp.content[0].text)
    except Exception as e:
        return {'_error': str(e)}
    return {}


# ---- OCR offline (PaddleOCR) ----
_paddle = None
def read_label_offline(bgr_image):
    global _paddle
    try:
        if _paddle is None:
            from paddleocr import PaddleOCR
            _paddle = PaddleOCR(use_angle_cls=True, lang='es', show_log=False)
        res = _paddle.ocr(bgr_image, cls=True)
        lines = []
        for block in (res or []):
            for ln in (block or []):
                try:
                    lines.append(ln[1][0])
                except Exception:
                    pass
        text = '\n'.join(lines)
        out = {'recipient_name': '', 'casillero': '', 'content': '', 'supplier': '', '_raw': text}
        mcas = re.search(r'\b([A-Z]-?\d{4,8})\b', text)
        if mcas:
            out['casillero'] = mcas.group(1)
        return out
    except Exception as e:
        return {'_error': str(e)}


def read_label(bgr_image, mode, keys):
    """Online primero; si falla o es offline, OCR local."""
    if mode in ('gemini', 'openai', 'claude'):
        data = read_label_ai(bgr_image, mode, keys)
        if data and not data.get('_error'):
            return data
    return read_label_offline(bgr_image)
