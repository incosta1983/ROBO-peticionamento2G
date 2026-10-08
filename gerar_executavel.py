"""Construção em Windows; não confundir com um binário já validado."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    if sys.platform != 'win32':
        raise SystemExit('O executável Windows deve ser gerado em Windows. Não há compilação cruzada neste script.')
    browser = ROOT / '.build-browsers'
    environment = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(browser))
    subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], cwd=ROOT, env=environment, check=True)
    if not any(browser.glob('chromium-*')):
        raise RuntimeError('O navegador não foi instalado; a construção foi cancelada.')
    # Saída exclusiva: nunca apagar a versão anterior, que pode conter DLLs em uso.
    output_root = ROOT / 'dist'
    output_root.mkdir(exist_ok=True)
    version = Path(tempfile.mkdtemp(prefix='v', dir=output_root))
    build_root = ROOT / 'build' / version.name
    build_root.mkdir(parents=True)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
               '--name', 'EPROC-Peticionamento', '--collect-all', 'playwright',
               '--distpath', str(version), '--workpath', str(build_root / 'work'), '--specpath', str(build_root),
               '--add-data', f'{ROOT / "web"};web',
               '--add-data', f'{ROOT / "modelo_peticionamento_eproc_2g.xlsx"};.',
               '--add-data', f'{browser};browsers', str(ROOT / 'executavel.py')]
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    distribution = version / 'EPROC-Peticionamento'
    if not (distribution / 'EPROC-Peticionamento.exe').is_file():
        raise RuntimeError('Executável não encontrado ao terminar a construção.')
    (distribution / 'LEIA-ME.txt').write_text(
        'EPROC Peticionamento - Windows\n\n'
        'Abra EPROC-Peticionamento.exe com dois cliques. A interface abre no navegador.\n'
        'Mantenha toda esta pasta, incluindo _internal. Não copie somente o .exe.\n'
        'Não é necessário instalar Python, PowerShell ou Java no computador de uso.\n'
        'A conexão com o EPROC continua sendo necessária para executar o lote.\n'
        'Use Encerrar programa na interface após terminar ou interromper o lote.\n'
        'Este pacote deve ser testado no Windows antes de ser distribuído.\n', encoding='utf-8')
    archive = shutil.make_archive(str(output_root / ('EPROC-Peticionamento-' + version.name)), 'zip',
                                 root_dir=version, base_dir='EPROC-Peticionamento')
    launcher = '@echo off\r\nstart "" "%~dp0dist\\' + version.name + '\\EPROC-Peticionamento\\EPROC-Peticionamento.exe"\r\n'
    (ROOT / 'abrir_ultima_versao.bat').write_bytes(launcher.encode('ascii'))
    print('Abra a versão nova com abrir_ultima_versao.bat. Encerre o programa anterior antes de abrir.')
    print('Executável gerado:', distribution / 'EPROC-Peticionamento.exe')
    print('Pacote para distribuição:', archive)

if __name__ == '__main__':
    main()
