"""Cliente de la API de estación de Simplex (auth por X-Station-Token)."""
import requests


class Simplex:
    def __init__(self, base_url: str, token: str):
        self.base = base_url.rstrip('/')
        self.s = requests.Session()
        self.s.headers['X-Station-Token'] = token

    def _get(self, path, **params):
        r = self.s.get(self.base + path, params=params, timeout=20)
        try:
            return r.json()
        except Exception:
            return {'success': False, 'message': f'HTTP {r.status_code}'}

    def _post(self, path, payload):
        r = self.s.post(self.base + path, json=payload, timeout=30)
        try:
            return r.json()
        except Exception:
            return {'success': False, 'message': f'HTTP {r.status_code}'}

    def client_search(self, q):
        return self._get('/api/station/client-search', q=q)

    def containers(self):
        return self._get('/api/station/containers', type='embarque', status='abierto')

    def container_create(self, code=''):
        return self._post('/api/station/container-create', {'type': 'embarque', 'code': code})

    def intake_pending(self):
        return self._get('/api/station/intake-pending')

    def package_create(self, payload):
        return self._post('/api/station/package-create', payload)
