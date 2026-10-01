"""Balanza USB PS60 (HID POS). Lee el peso y lo convierte a libras."""

UNIT_TO_LB = {2: 1/453.59237, 3: 2.2046226218, 11: 1/16, 12: 1.0}  # gramo, kg, onza, libra

def _open(vendor=None, product=None):
    import hid
    if vendor and product:
        h = hid.device(); h.open(int(vendor, 16), int(product, 16)); return h
    # Autodetección: toma el primer dispositivo con usage_page de báscula (0x8D) o el primer HID plausible.
    for d in hid.enumerate():
        try:
            if d.get('usage_page') == 0x8D:
                h = hid.device(); h.open_path(d['path']); return h
        except Exception:
            pass
    return None

def read_weight_lb(vendor=None, product=None, tries=15):
    """Devuelve (lb:float|None, stable:bool, msg:str)."""
    try:
        import hid  # noqa
    except Exception:
        return None, False, 'hidapi no instalado'
    h = None
    try:
        h = _open(vendor, product)
        if not h:
            return None, False, 'balanza no encontrada'
        h.set_nonblocking(1)
        last = None
        for _ in range(tries):
            data = h.read(8, timeout_ms=200)
            if data and len(data) >= 6:
                # [reportId?, status, unit, exp, lsbb, msb] — formato HID POS típico
                off = 1 if len(data) >= 6 else 0
                status = data[off]; unit = data[off+1]
                exp = data[off+2] - 256 if data[off+2] > 127 else data[off+2]
                raw = data[off+3] + data[off+4] * 256
                lb = UNIT_TO_LB.get(unit, 1.0) * raw * (10 ** exp)
                lb = round(max(0.0, lb), 2)
                last = lb
                if status in (2, 4):  # estable
                    return lb, True, 'estable'
        return last, False, 'leído (no estable)' if last is not None else 'sin lectura'
    except Exception as e:
        return None, False, str(e)
    finally:
        try:
            if h: h.close()
        except Exception:
            pass
