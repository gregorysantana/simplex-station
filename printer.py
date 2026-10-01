"""Impresión de etiqueta 4x3 con código de barras de la guía."""
import os, sys, tempfile, subprocess

def _render_label_png(label: dict) -> str:
    """Genera un PNG de etiqueta 4x3in con el barcode de la guía. Devuelve la ruta."""
    from PIL import Image, ImageDraw, ImageFont
    import barcode
    from barcode.writer import ImageWriter

    guia = str(label.get('guia', ''))
    W, H = 1200, 900  # 4x3 in @ 300dpi
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    try:
        f_big = ImageFont.truetype('Arial.ttf', 60)
        f_mid = ImageFont.truetype('Arial.ttf', 40)
    except Exception:
        f_big = ImageFont.load_default(); f_mid = f_big

    branch = str(label.get('branch_code') or (label.get('branch_name') or '')[:4])
    courier = str(label.get('branch_label_code') or label.get('courier_code') or '')
    d.text((30, 20), branch, fill='black', font=f_big)
    d.text((W-260, 20), courier, fill='black', font=f_big)

    # Barcode Code128 de la guía
    try:
        code128 = barcode.get('code128', guia, writer=ImageWriter())
        bc = code128.render({'module_height': 18.0, 'font_size': 0, 'quiet_zone': 2.0, 'write_text': False})
        bc = bc.resize((W-120, 240))
        img.paste(bc, (60, 150))
    except Exception:
        d.text((60, 220), guia, fill='black', font=f_big)
    d.text((60, 410), guia, fill='black', font=f_mid)

    d.text((30, 520), f"PESO: {label.get('weight_lb','')} LBS", fill='black', font=f_mid)
    d.text((30, 580), f"CLIENTE: {label.get('client_code','')}", fill='black', font=f_mid)
    d.text((30, 640), f"SUPLIDOR: {str(label.get('supplier_name') or '')[:24]}", fill='black', font=f_mid)

    path = os.path.join(tempfile.gettempdir(), f"label_{guia or 'x'}.png")
    img.save(path)
    return path

def print_label(label: dict, printer: str = '') -> tuple:
    """Imprime la etiqueta. Devuelve (ok, mensaje)."""
    try:
        path = _render_label_png(label)
    except Exception as e:
        return False, f'no se pudo renderizar: {e}'
    try:
        if sys.platform.startswith('win'):
            os.startfile(path, 'print')  # noqa (Windows)
        elif sys.platform == 'darwin' or sys.platform.startswith('linux'):
            cmd = ['lp']
            if printer:
                cmd += ['-d', printer]
            cmd.append(path)
            subprocess.run(cmd, check=True)
        else:
            return False, 'SO no soportado'
        return True, 'enviado a impresora'
    except Exception as e:
        return False, str(e)
