import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from openpyxl import Workbook
from controle import Controle, REQUIRED, OUTPUTS
from robo import run_batch, SubjectCompetenceError

class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name); pdf=root/'peticao.pdf'; pdf.write_bytes(b'%PDF-1.4\n')
        self.path=root/'trabalho.xlsx'
        record=dict.fromkeys(REQUIRED+OUTPUTS,'')
        record.update(CLASSE_PROCESSUAL='MANDADO DE SEGURANÇA CÍVEL',CODIGO_ASSUNTO='0219032307',
                      TIPO_PARTE_ATIVA='Pessoa Física',CPF_CNPJ_ATIVA='01234567890',
                      TIPO_PARTE_PASSIVA='Entidade',NOME_ENTIDADE_PASSIVA='ENTIDADE TESTE',CAMINHO_PETICAO=str(pdf))
        book=Workbook(); sheet=book.active; sheet.title='Registros'; sheet.append(REQUIRED+OUTPUTS)
        for id in ['001','002']:
            record['ID_REGISTRO']=id; sheet.append([record[k] for k in REQUIRED+OUTPUTS])
        book.save(self.path); self.control=Controle(self.path)
        self.bot=MagicMock(); self.bot.stage='Informações'; self.bot.submitted=False
        self.bot.result.return_value=(MagicMock(),'4009866-56.2026.8.26.0000','Magistrado Teste')
        self.events=[]

    def execute(self,confirm=lambda record:True,stop=lambda:False,limit=None):
        with patch('robo.sync_playwright') as pw, patch('robo.Robo',return_value=self.bot):
            run_batch(self.control,'teste','senha-fixture',confirm,self.events.append,stop,limit=limit)
            pw.return_value.__enter__.return_value.chromium.launch.return_value.close.assert_called_once()

    def statuses(self):
        return [record['STATUS'] for _,record in Controle(self.path).rows()]

    def test_limit_includes_failed_attempts(self):
        self.bot.information.side_effect=ValueError('Falha no primeiro registro')
        self.execute(limit=1)
        self.assertEqual(self.statuses(),['Erro',''])
        self.assertEqual(self.bot.start.call_count,1)
        self.assertEqual(self.events[0]['total'],1)

    def test_limit_leaves_remaining_rows_untouched(self):
        self.execute(limit=1)
        self.assertEqual(self.statuses(),['Concluído',''])
        self.assertEqual(self.bot.start.call_count,1)

    def test_error_continues_to_next_record(self):
        self.bot.information.side_effect=[ValueError('Falha antes de ajuizar'),None]
        self.execute()
        self.assertEqual(self.statuses(),['Erro','Concluído'])
        self.assertEqual(self.bot.start.call_count,2)
        self.assertEqual(self.bot.confirmation.return_value.click.call_count,1)

    def test_browser_stays_open_between_subject_failure_and_next_row(self):
        with patch('robo.sync_playwright') as pw, patch('robo.Robo',return_value=self.bot):
            browser=pw.return_value.__enter__.return_value.chromium.launch.return_value
            self.bot.subjects.side_effect=[SubjectCompetenceError('Não há nenhuma competência associada'),None]
            def start_next():
                browser.close.assert_not_called()
            self.bot.start.side_effect=start_next
            run_batch(self.control,'teste','senha-fixture',lambda record:True,self.events.append,limit=2)
            self.assertEqual(self.statuses(),['Erro','Concluído'])
            browser.close.assert_called_once()
            self.assertEqual(self.bot.start.call_count,2)
            self.bot.abort_petition.assert_called_once()

    def test_subject_without_competence_is_recorded_and_next_runs(self):
        self.bot.subjects.side_effect=[SubjectCompetenceError('Não há nenhuma competência associada a este assunto principal na área Direito Privado.'),None]
        self.execute()
        self.assertEqual(self.statuses(),['Erro','Concluído'])
        self.bot.abort_petition.assert_called_once()
        self.assertEqual(self.bot.start.call_count,2)
        self.assertIn('competência',next(Controle(self.path).rows())[1]['MENSAGEM_ERRO'])

    def test_document_error_cancels_before_starting_next_record(self):
        self.bot.documents.side_effect=[RuntimeError('Aviso do sistema: Documento 1 não informado.'),None]
        self.execute()
        self.assertEqual(self.statuses(),['Erro','Concluído'])
        self.bot.abort_petition.assert_called_once()
        calls=[call[0] for call in self.bot.mock_calls]
        self.assertLess(calls.index('abort_petition'),len(calls)-1-calls[::-1].index('start'))
        self.assertIn('Documento 1 não informado',next(Controle(self.path).rows())[1]['MENSAGEM_ERRO'])

    def test_cancellation_failure_stops_before_next_record(self):
        self.bot.documents.side_effect=RuntimeError('Documento 1 não informado.')
        self.bot.abort_petition.side_effect=RuntimeError('Cancelamento indisponível')
        with self.assertRaisesRegex(RuntimeError,'cancelar o rascunho'):self.execute()
        self.assertEqual(self.statuses(),['Erro',''])
        self.assertEqual(self.bot.start.call_count,1)

    def test_uncertain_submit_is_recorded_and_next_record_runs(self):
        self.bot.confirmation.return_value.click.side_effect=[RuntimeError('Resposta perdida'),None]
        self.execute()
        self.assertEqual(self.statuses(),['Verificar protocolo','Concluído'])
        self.assertFalse(Controle(self.path).eligible(next(Controle(self.path).rows())[1]))

    def test_declined_confirmation_stops_before_next_record(self):
        self.execute(confirm=lambda record:False)
        self.assertEqual(self.statuses(),['Erro',''])
        self.bot.confirmation.return_value.click.assert_not_called()
        self.assertEqual(self.bot.start.call_count,1)

    def test_stop_finishes_current_without_starting_next(self):
        stop={'value':False}
        def result():
            stop['value']=True
            return MagicMock(),'4009866-56.2026.8.26.0000','Magistrado Teste'
        self.bot.result.side_effect=result
        self.execute(stop=lambda:stop['value'])
        self.assertEqual(self.statuses(),['Concluído',''])
        self.assertEqual(self.bot.start.call_count,1)

if __name__=='__main__': unittest.main()
