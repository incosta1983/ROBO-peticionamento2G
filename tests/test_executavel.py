import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import executavel
import gerar_executavel

class ExecutableTests(unittest.TestCase):
    def test_packaged_browser_uses_internal_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'browsers').mkdir()
            with patch.object(executavel.sys,'frozen',True,create=True), patch.object(executavel.sys,'_MEIPASS',tmp,create=True), patch.dict(os.environ):
                executavel.configure_browser()
                self.assertEqual(os.environ['PLAYWRIGHT_BROWSERS_PATH'],str(root/'browsers'))

    def test_incomplete_executable_folder_has_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(executavel.sys,'frozen',True,create=True), patch.object(executavel.sys,'_MEIPASS',tmp,create=True):
            with self.assertRaisesRegex(RuntimeError,'pasta interna'):
                executavel.configure_browser()

    def test_second_launch_opens_existing_interface(self):
        response=MagicMock(); response.status=200
        response.read.return_value='<title>EPROC · Peticionamento</title><meta name="app-token">'.encode()
        with patch('executavel.urlopen') as urlopen, patch('executavel.webbrowser.open') as browser:
            urlopen.return_value.__enter__.return_value=response
            self.assertTrue(executavel.existing_interface())
            browser.assert_called_once()

    def test_windows_build_is_not_claimed_on_linux(self):
        with patch.object(gerar_executavel.sys,'platform','linux'):
            with self.assertRaisesRegex(SystemExit,'Windows'):
                gerar_executavel.main()

    def test_windows_build_command_bundles_resources_without_replacing_old_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'.build-browsers'/'chromium-1208').mkdir(parents=True)
            old=root/'dist'/'EPROC-Peticionamento'; old.mkdir(parents=True)
            dll=old/'chrome.dll'; dll.write_bytes(b'versao-anterior')
            def simulate_build(command, **kwargs):
                if 'PyInstaller' in command:
                    output=Path(command[command.index('--distpath')+1])/'EPROC-Peticionamento'
                    output.mkdir()
                    # Marcador somente para teste; não é executável Windows.
                    (output/'EPROC-Peticionamento.exe').touch()
            with patch.object(gerar_executavel,'ROOT',root),patch.object(gerar_executavel.sys,'platform','win32'),patch('gerar_executavel.subprocess.run',side_effect=simulate_build) as run,patch('gerar_executavel.shutil.make_archive',return_value='pacote.zip'),patch('builtins.print'):
                gerar_executavel.main()
                command=run.call_args_list[1].args[0]
                self.assertIn('--windowed',command)
                self.assertIn('--onedir',command)
                self.assertIn(str(root/'.build-browsers')+';browsers',command)
                first=Path(command[command.index('--distpath')+1])
                self.assertTrue((first/'EPROC-Peticionamento'/'LEIA-ME.txt').exists())
                gerar_executavel.main()
                second_command=run.call_args_list[3].args[0]
                second=Path(second_command[second_command.index('--distpath')+1])
                self.assertNotEqual(first,second)
                self.assertEqual(dll.read_bytes(),b'versao-anterior')
                self.assertIn(second.name,(root/'abrir_ultima_versao.bat').read_text())

if __name__=='__main__': unittest.main()
