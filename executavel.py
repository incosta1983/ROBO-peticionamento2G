"""Entrada do executável Windows: recursos e Chromium incluídos no pacote."""
import os
import sys
import webbrowser
from pathlib import Path
from urllib.request import urlopen


def configure_browser():
    if getattr(sys, 'frozen', False):
        bundle = Path(sys._MEIPASS)
        browsers = bundle / 'browsers'
        if not browsers.is_dir():
            raise RuntimeError('A pasta interna do navegador não foi encontrada. Extraia a pasta completa do pacote.')
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browsers)


def existing_interface():
    url = 'http://127.0.0.1:8765/'
    try:
        with urlopen(url, timeout=2) as response:
            html = response.read(50000).decode('utf-8')
            if response.status == 200 and '<title>EPROC · Peticionamento</title>' in html and 'name="app-token"' in html:
                webbrowser.open(url)
                return True
    except (OSError, ValueError):
        pass
    return False


def main():
    try:
        configure_browser()
        if existing_interface():
            return
        from interface import main as start
        try:
            start()
        except OSError:
            if not existing_interface():
                raise
    except Exception as exc:
        from tkinter import Tk, messagebox
        window = Tk(); window.withdraw()
        try:
            messagebox.showerror('EPROC Peticionamento', 'Não foi possível iniciar o programa.\n\n' + str(exc), parent=window)
        finally:
            window.destroy()

if __name__ == '__main__':
    main()
