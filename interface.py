"""Interface web local para Windows. Execute: python interface.py."""
import argparse
import hmac
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from controle import Controle, validate
from robo import run_batch

ROOT = Path(__file__).resolve().parent

def read_records(path):
    control = Controle(path, persist=False)
    records = []
    for row, record in control.rows():
        eligible = control.eligible(record)
        error = ''
        if eligible:
            try:
                validate(record, control.path.parent)
            except ValueError as exc:
                error = str(exc)
        records.append({'row': row, 'id': record['ID_REGISTRO'], 'class': record['CLASSE_PROCESSUAL'],
                        'status': record['STATUS'] or 'Pendente', 'eligible': eligible,
                        'error': error or record['MENSAGEM_ERRO'], 'valid': not bool(error),
                        'stage': record['ETAPA_ERRO'], 'process': record['NUMERO_PROCESSO_GERADO'],
                        'judge': record['MAGISTRADO']})
    return records

class Manager:
    def __init__(self, runner=run_batch):
        self.runner = runner
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.stop_event = threading.Event()
        self.busy = False
        self.answer = None
        self.thread = None
        self.state = self.empty_state()

    @staticmethod
    def empty_state():
        return {'phase': 'idle', 'stage': '', 'current': '', 'total': 0,
                'path': '', 'rows': [], 'confirmation': None, 'message': '', 'logs': []}

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state, ensure_ascii=False))

    def inspect(self, path):
        with self.lock:
            if self.busy:
                raise ValueError('Aguarde o lote atual terminar antes de validar outra planilha.')
            self.busy = True
        try:
            rows = read_records(path)
            with self.lock:
                self.state = {**self.empty_state(), 'phase': 'validated', 'path': str(Path(path).resolve()),
                              'rows': rows, 'total': sum(r['eligible'] for r in rows),
                              'message': 'Validação concluída. Confira os registros antes de iniciar.'}
                return self.snapshot()
        finally:
            with self.lock:
                self.busy = False

    def start(self, path, user, password, automatic=True, limit=50, diagnostic=False):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError('O limite deve ser um número inteiro maior que zero.')
        if not isinstance(diagnostic, bool) or (diagnostic and limit != 1):
            raise ValueError('O diagnóstico com navegador aberto requer limite de 1 registro.')
        if not user.strip() or not password:
            raise ValueError('Informe usuário e senha.')
        with self.lock:
            if self.busy:
                raise ValueError('Já existe uma operação em andamento.')
            self.busy = True
            try:
                rows = read_records(path)
                if not any(r['eligible'] for r in rows):
                    raise ValueError('Não há registros pendentes elegíveis nesta planilha.')
                planned = [r for r in rows if r['eligible']][:limit]
                for r in rows:
                    r['in_batch'] = r in planned
                self.stop_event.clear()
                self.state = {**self.empty_state(), 'phase': 'running', 'path': str(Path(path).resolve()),
                              'rows': rows, 'total': len(planned), 'limit': limit,
                              'message': 'Abrindo o navegador para autenticação.'}
                self.thread = threading.Thread(target=self._work, args=(path, user, password, automatic, limit, diagnostic), daemon=False)
                self.thread.start()
            except Exception:
                self.busy = False
                raise

    def _work(self, path, user, password, automatic, limit, diagnostic):
        try:
            control = Controle(path)
            def confirmation(record):
                if automatic:
                    return not self.stop_event.is_set()
                with self.condition:
                    self.answer = None
                    self.state['phase'] = 'confirmation'
                    self.state['confirmation'] = {'id': secrets.token_urlsafe(24), 'record': record['ID_REGISTRO']}
                    self.state['message'] = 'Confira o resumo na janela do EPROC e confirme o ajuizamento aqui.'
                    self.condition.wait_for(lambda: self.answer is not None or self.stop_event.is_set())
                    answer = self.answer is True and not self.stop_event.is_set()
                    self.state['confirmation'] = None
                    self.state['phase'] = 'stopping' if self.stop_event.is_set() else 'running'
                    return answer
            def inspect_failure(stage, message):
                with self.condition:
                    self.state['phase'] = 'diagnostic'
                    self.state['stage'] = stage
                    self.state['message'] = message.replace(password, '[senha ocultada]') if password else message
                    self.condition.wait_for(self.stop_event.is_set)
                    self.state['phase'] = 'stopping'
            options = {'limit': limit}
            if diagnostic:
                options['on_failure'] = inspect_failure
            self.runner(control, user, password, confirmation, self.on_progress, self.stop_event.is_set, **options)
            with self.lock:
                self.state['phase'] = 'stopped' if self.stop_event.is_set() else 'finished'
                self.state['message'] = 'Lote interrompido; confira os resultados.' if self.stop_event.is_set() else 'Lote encerrado. Confira resultados e eventuais erros.'
        except Exception as exc:
            with self.lock:
                self.state['phase'] = 'failed'
                message = str(exc).replace(password, '[senha ocultada]') if password else str(exc)
                self.state['message'] = message[:2000]
        finally:
            password = ''
            with self.lock:
                self.busy = False
                self.state['confirmation'] = None

    def on_progress(self, event):
        with self.lock:
            kind = event['event']
            if kind == 'batch':
                self.state['total'] = event['total']
            elif kind == 'stage':
                self.state['stage'] = event['stage']
                self.state['logs'].append((self.state['current'] or 'Preparação') + ' — ' + event['stage'])
                self.state['logs'] = self.state['logs'][-200:]
            elif kind == 'log':
                self.state['logs'].append(event['message'])
                self.state['logs'] = self.state['logs'][-200:]
            elif kind == 'current':
                self.state['current'] = event['id']
            elif kind == 'row':
                for row in self.state['rows']:
                    if row['row'] == event['row']:
                        row['attempted'] = True
                        for field in ['status', 'stage', 'process', 'judge', 'error']:
                            if field in event:
                                row[field] = event[field]
                        if event['status'] == 'Em execução':
                            row['error'] = ''; row['stage'] = ''
                        break
                self.state['logs'].append(f"{event['id']}: {event['status']}" + (f" — {event['stage']}" if event.get('stage') else ''))
                self.state['logs'] = self.state['logs'][-200:]

    def confirm(self, confirmation_id):
        with self.condition:
            pending = self.state['confirmation']
            if self.state['phase'] != 'confirmation' or not pending or not hmac.compare_digest(str(confirmation_id), pending['id']):
                raise ValueError('Esta confirmação expirou ou não corresponde ao registro atual.')
            if self.answer is not None or self.stop_event.is_set():
                raise ValueError('A confirmação já foi respondida ou a parada foi solicitada.')
            self.answer = True
            self.condition.notify_all()

    def stop(self):
        with self.condition:
            if not self.busy:
                raise ValueError('Não há lote em andamento.')
            self.stop_event.set()
            self.state['phase'] = 'stopping'
            self.state['message'] = 'Parada solicitada. O registro em curso será concluído; se ainda aguarda confirmação, não será ajuizado.'
            self.condition.notify_all()


def choose_file():
    import tkinter as tk
    from tkinter import filedialog
    window = tk.Tk(); window.withdraw(); window.attributes('-topmost', True)
    try:
        return filedialog.askopenfilename(title='Escolher planilha de peticionamento', filetypes=[('Planilhas Excel', '*.xlsx')])
    finally:
        window.destroy()

class LocalServer(ThreadingHTTPServer):
    def __init__(self, address, manager=None):
        super().__init__(address, Handler)
        self.manager = manager or Manager()
        self.exiting = False
        self.token = secrets.token_urlsafe(32)
        self.allowed_hosts = {f'127.0.0.1:{self.server_port}', f'localhost:{self.server_port}'}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Não registrar URLs, dados da planilha ou credenciais.
        pass

    def respond(self, status, body, content_type='application/json; charset=utf-8'):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(raw)

    def permitted(self, api=False):
        if self.headers.get('Host', '') not in self.server.allowed_hosts:
            self.respond(403, {'error': 'Endereço local inválido.'}); return False
        origin = self.headers.get('Origin')
        if origin and origin not in {'http://' + host for host in self.server.allowed_hosts}:
            self.respond(403, {'error': 'Origem não autorizada.'}); return False
        if api and not hmac.compare_digest(self.headers.get('X-App-Token', ''), self.server.token):
            self.respond(403, {'error': 'Atualize a página para iniciar uma sessão local.'}); return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.permitted(path.startswith('/api/')):
            return
        if path == '/api/state':
            self.respond(200, self.server.manager.snapshot())
        elif path == '/modelo.xlsx':
            self.respond(200, (ROOT / 'modelo_peticionamento_eproc_2g.xlsx').read_bytes(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        elif path in ['/', '/app.js', '/style.css']:
            name = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[path]
            body = (ROOT / 'web' / name).read_bytes()
            if path == '/':
                body = body.replace(b'__APP_TOKEN__', self.server.token.encode())
            types = {'/': 'text/html; charset=utf-8', '/app.js': 'text/javascript; charset=utf-8', '/style.css': 'text/css; charset=utf-8'}
            self.respond(200, body, types[path])
        else:
            self.respond(404, {'error': 'Página não encontrada.'})

    def do_POST(self):
        if not self.permitted(api=True):
            return
        try:
            if self.server.exiting:
                raise ValueError('O programa está sendo encerrado.')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Formato de requisição inválido.')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise ValueError('Requisição inválida ou muito grande.')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Requisição inválida.')
            path = urlsplit(self.path).path
            manager = self.server.manager
            if path == '/api/select':
                self.respond(200, {'path': choose_file()})
            elif path == '/api/validate':
                self.respond(200, manager.inspect(body['path']))
            elif path == '/api/start':
                if not isinstance(body.get('automatic', True), bool):
                    raise ValueError('Modo de confirmação inválido.')
                manager.start(body['path'], body['user'], body['password'], body.get('automatic', True), body.get('limit', 50), body.get('diagnostic', False))
                self.respond(200, {'ok': True})
            elif path == '/api/confirm':
                manager.confirm(body['confirmation_id']); self.respond(200, {'ok': True})
            elif path == '/api/exit':
                with manager.lock:
                    if manager.busy:
                        raise ValueError('Interrompa o lote e aguarde o término antes de encerrar o programa.')
                    self.server.exiting = True
                self.respond(200, {'ok': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            elif path == '/api/stop':
                manager.stop(); self.respond(200, {'ok': True})
            else:
                self.respond(404, {'error': 'Ação não encontrada.'})
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.respond(400, {'error': str(exc)[:1000]})
        except Exception:
            self.respond(500, {'error': 'Não foi possível executar a ação. Confira a planilha e o acesso aos arquivos.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--sem-abrir', action='store_true', help='Não abrir o navegador automaticamente')
    args = parser.parse_args()
    with LocalServer(('127.0.0.1', args.port)) as server:
        url = f'http://127.0.0.1:{server.server_port}/'
        print('Interface local em execução. Mantenha esta janela aberta. Feche após terminar o lote.')
        print(url)
        if not args.sem_abrir:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            # Não interromper o registro atual; o worker permanece vivo até concluir.
            if server.manager.busy:
                server.manager.stop()
            if server.manager.thread:
                server.manager.thread.join()

if __name__ == '__main__':
    main()
