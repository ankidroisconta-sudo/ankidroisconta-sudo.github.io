import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from urllib.request import urlopen

from werkzeug.serving import make_server
from app import app, autopilot_loop, worker

PORTS = range(8765, 8775)


def open_browser(url):
    """Abre o estúdio numa janela anônima do Chrome (extensões não interferem). Sem Chrome, usa o navegador padrão."""
    candidates = [shutil.which('chrome'), shutil.which('google-chrome')]
    for base in (os.environ.get('PROGRAMFILES', ''), os.environ.get('PROGRAMFILES(X86)', ''), os.environ.get('LOCALAPPDATA', '')):
        if base:
            candidates.append(os.path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe'))
    for exe in candidates:
        if exe and os.path.isfile(exe):
            try:
                subprocess.Popen([exe, '--incognito', '--new-window', url])
                return
            except OSError:
                pass
    webbrowser.open(url)


def already_running(port):
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/state", timeout=1) as response:
            return "templates" in json.load(response)
    except Exception:
        return False


if __name__ == "__main__":
    for port in PORTS:
        url = f"http://127.0.0.1:{port}"
        if already_running(port):
            open_browser(url)
            print("O Estúdio Livre já estava aberto em", url)
            sys.exit(0)
        try:
            server = make_server("127.0.0.1", port, app, threaded=True)
        except OSError:
            continue  # porta ocupada por outro programa
        threading.Thread(target=worker, daemon=True).start()
        threading.Thread(target=autopilot_loop, daemon=True).start()
        threading.Timer(0.8, open_browser, (url,)).start()
        print(f"Estúdio Livre aberto em {url}")
        print("Mantenha esta janela aberta durante a produção. Para sair, feche-a.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        sys.exit(0)
    print("Nenhuma porta livre entre 8765 e 8774. Feche outros programas e tente de novo.")
    sys.exit(1)
