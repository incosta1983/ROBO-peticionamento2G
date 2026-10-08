"""Teste funcional isolado: nenhum pedido sai para o TJSP."""
import os
import tempfile
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
from robo import Robo, MP, SubjectCompetenceError

HEADER = '<meta charset="utf-8">'

def fixture(stage):
    if stage == 'menu':
        return '<input id="sidebar-searchbox"><a aria-label="Petição Inicial" href="/info">Petição Inicial</a>'
    if stage in ['info', 'expanded']:
        return '''<select id="selLocalidadeJudicial"><option value="400">TJSP</option></select>
        <input type="checkbox" id="btnPredicao"><select id="selIdGrupoCompetencia"><option>Direito Privado</option></select>
        <select id="selIdClasseJudicial" onchange="location.href='/expanded'"><option></option><option>MANDADO DE SEGURANÇA CÍVEL</option></select>
        <select id="selTipoJustica"><option value="1">TJSP - PRIMEIRO GRAU</option></select>
        <input id="txtProcessoOriginario" onblur="document.querySelector('#txtDescJuizo').value='Juízo Teste'">
        <input id="txtDescJuizo" readonly><input type="checkbox" id="chkRemeterPlantao" checked>
        <input type="checkbox" id="chkNaoAplicaValor"><button id="btnSalvar" onclick="location.href='/subjects'">Próxima</button>'''
    if stage == 'subjects':
        return '''<label><input type="radio" name="mode">Assunto</label><input id="txtFiltroPesquisa">
        <button id="btnFiltrar" onclick="document.querySelector('#divArvore').style.display='block'">Filtrar</button>
        <div id="divArvore" style="display:none"><a class="jstree-anchor" id="0219032307_anchor" onclick="window.selectedSubject='0219032307'">Despejo</a></div>
        <input id="txtDesAssunto" readonly><img alt="Incluir assunto" id="imgIncluir0219032307" onclick="if(window.selectedSubject==='0219032307') document.querySelector('#tblAssuntoPrincipal').innerHTML='<tr><td>0219032307 - Despejo</td></tr>'">
        <input id="hdnIdAssuntoPrincipal" type="hidden" value="82401842"><table id="tblAssuntoPrincipal"></table><select id="selNumCodCompetencia"><option>Direito Privado</option></select>
        <button id="sbmProcessoEtapa2" onclick="location.href='/active'">Próxima</button>'''
    if stage in ['active','passive']:
        active = stage == 'active'
        identity = '012.345.678-90' if active else MP
        table = f'''<table id="tblResultadosBusca" {'style="display:none"' if active else ''}><tbody><tr><td>{identity}</td><td>
        <select id="selPrincipal0"><option value="N">Não</option><option value="S">Sim</option></select>
        <button id="btnIncluir" onclick="include()">Incluir</button></td></tr></tbody></table>'''
        return f'''<select id="selTipoPessoa"><option value="PF">Pessoa Física</option><option value="ENT">Entidade</option></select>
        <input id="txtCpfCnpj"><button id="btnConsultar" onclick="document.querySelector('#tblResultadosBusca').style.display='table'">Consultar</button>{table}
        <table id="tblPartes"><tbody></tbody></table><button id="btnProxima" onclick="location.href='/{'passive' if active else 'docs'}'">Próxima</button>
        <script>function include(){{document.querySelector('#tblPartes tbody').innerHTML=`<tr><td>{identity}</td><td><button class='btn-sin-principal'>Sim</button><select id='selJusticaAutor1'><option>Não Requerida</option><option>Requerida</option></select></td></tr>`;}}</script>'''
    if stage == 'docs':
        return '''<input type="file"><input id="txtTipo_1" oninput="document.querySelector('#divInfraAjaxtxtTipo_1').style.display='block'">
        <input type="hidden" id="selTipoArquivo_1"><div id="divInfraAjaxtxtTipo_1" style="display:none"><a onclick="document.querySelector('#selTipoArquivo_1').value='1'">PETIÇÃO INICIAL</a></div>
        <select id="selIdSigilo_1"><option>Sem Sigilo (Nível 0)</option></select>
        <button id="btnEnviarArquivos" onclick="document.querySelector('#tbDocumentosCadastradas').innerHTML='<tr><td><a href=&quot;#&quot;>peticao.pdf</a></td><td>100 bytes</td><td>INIC</td></tr>'">Confirmar</button>
        <table id="tbDocumentosCadastradas"></table><button id="btnSalvar" onclick="document.querySelector('iframe').src='/confirm'">Finalizar</button><iframe></iframe>'''
    if stage == 'confirm':
        return '<button id="sbmConfirmar" onclick="parent.location.href=\'/result\'">Confirmar ajuizamento</button>'
    if stage == 'result':
        return '<h2 id="divDesProcessoEnviado">Processo distribuído.</h2><a id="lblDesNumProcesso">4009866-56.2026.8.26.0000</a><span id="lblDesJuiz">Magistrado Teste - Gabinete - Câmara</span><button id="btnFechar" onclick="location.href=\'/menu\'">Fechar</button>'
    return ''

class BrowserTests(unittest.TestCase):
    def test_information_with_visible_absent_or_hidden_value_checkbox(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            for mode in ['visible', 'absent', 'hidden']:
                with self.subTest(mode=mode):
                    page=browser.new_page()
                    page.set_default_timeout(2000)
                    html=fixture('expanded').replace('MANDADO DE SEGURANÇA CÍVEL', 'PETIÇÃO CÍVEL')
                    if mode == 'absent':
                        html=html.replace('<input type="checkbox" id="chkNaoAplicaValor">', '')
                    elif mode == 'hidden':
                        html=html.replace('id="chkNaoAplicaValor"', 'id="chkNaoAplicaValor" style="display:none"')
                    html=html.replace("location.href='/subjects'", "location.href='/subjects?checked='+String(document.querySelector('#chkNaoAplicaValor')?.checked)")
                    page.route('**/info',lambda route:route.fulfill(content_type='text/html; charset=utf-8',body=fixture('info').replace('MANDADO DE SEGURANÇA CÍVEL', 'PETIÇÃO CÍVEL')))
                    page.route('**/expanded',lambda route:route.fulfill(content_type='text/html; charset=utf-8',body=html))
                    checked=[]
                    def subjects(route):
                        checked.append(route.request.url.split('checked=')[-1])
                        route.fulfill(content_type='text/html; charset=utf-8',body=fixture('subjects'))
                    page.route('**/subjects?checked=*',subjects)
                    page.goto('https://local.test/info')
                    Robo(page).information({'CLASSE_PROCESSUAL':'PETIÇÃO CÍVEL','PROCESSO_ORIGINARIO':''})
                    self.assertTrue(page.locator('#txtFiltroPesquisa').is_visible())
                    self.assertEqual(checked,['true' if mode == 'visible' else 'false' if mode == 'hidden' else 'undefined'])
                    page.close()
            browser.close()

    def test_cancel_subject_error_can_return_to_initial_form(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            page.route('**/info',lambda route:route.fulfill(content_type='text/html',body=fixture('info')))
            page.goto('https://local.test/info')
            page.set_content("""<input id="txtFiltroPesquisa" value="02190305"><span>Não há nenhuma competência associada a este assunto principal</span>
                <button id="btnCancelar" onclick="if(confirm('Confirma encerrar esta operação?')) location.href='/info'">Cancelar</button>""")
            bot=Robo(page);bot.abort_petition()
            self.assertTrue(page.locator('#selLocalidadeJudicial').is_visible())
            self.assertFalse(page.locator('#txtFiltroPesquisa').count())
            self.assertEqual(bot.alerts,[])
            browser.close()

    def test_subject_competence_warning_is_detected_before_selecting(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            page.set_content('<select id="selNumCodCompetencia"></select><span style="color:red">Não há nenhuma competência associada a este assunto principal na área "Direito Privado".<br>Por favor, volte para a etapa anterior e escolha outra área para peticionar.</span>')
            with self.assertRaisesRegex(SubjectCompetenceError,'Direito Privado'):Robo(page).select_private_competence()
            browser.close()

    def test_does_not_scroll_to_document_action_under_other_modal(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            page.set_content('<button id="btnSalvar" onclick="window.sent=true">Finalizar</button><div style="height:2500px"></div><div class="modal-backdrop" style="position:fixed;inset:0;z-index:100;background:gray"></div>')
            page.evaluate('window.scrollTo(0,800)');before=page.evaluate('window.scrollY')
            bot=Robo(page);original_wait=bot.wait
            bot.wait=lambda condition,message,timeout=60:original_wait(condition,message,timeout=.3)
            with self.assertRaisesRegex(TimeoutError,'permaneceu bloqueado'):bot.click_document_action('#btnSalvar')
            self.assertEqual(page.evaluate('window.scrollY'),before)
            self.assertFalse(page.evaluate('Boolean(window.sent)'))
            browser.close()

    def test_closes_visible_dialog_with_zero_size_modal_without_scroll(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            page.set_content("""<div style="height:2500px"></div>
                <div class="modal-backdrop" style="position:fixed;inset:0;background:gray;z-index:100"></div>
                <div id="modalPdfPesquisavel" style="width:0;height:0;overflow:visible">
                <div class="modal-content" style="position:fixed;top:50px;left:50px;width:300px;height:200px;z-index:200;background:white">
                Recomendamos que os arquivos PDFs enviados contenham texto pesquisável.
                <button class="close" data-dismiss="modal" aria-label="Close" onclick="document.querySelector('#modalPdfPesquisavel').style.display='none';document.querySelector('.modal-backdrop').remove()">X</button></div></div>""")
            page.evaluate('window.scrollTo(0,800)')
            before=page.evaluate('window.scrollY')
            self.assertFalse(page.locator('#modalPdfPesquisavel').is_visible())
            self.assertTrue(page.locator('button.close').is_visible())
            Robo(page).close_pdf_notice()
            self.assertFalse(page.locator('button.close').is_visible())
            self.assertEqual(page.evaluate('window.scrollY'),before)
            browser.close()

    def test_closes_pdf_notice_inside_frame(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page();page.set_content('<iframe></iframe>')
            page.frames[1].set_content("""<div id="modalPdfPesquisavel"><button class="close" data-dismiss="modal" aria-label="Close" onclick="this.parentElement.style.display='none'">X</button></div>""")
            Robo(page).close_pdf_notice()
            self.assertFalse(page.frames[1].locator('button.close').is_visible())
            browser.close()

    def test_closes_delayed_notice_after_confirming_documents(self):
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            pdf=Path(folder)/'peticao.pdf';pdf.write_bytes(b'%PDF-1.4\n')
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page();stages=[]
            html=fixture('docs').replace("onclick=\"document.querySelector('#tbDocumentosCadastradas')", "onclick=\"window.jQuery={active:1};setTimeout(()=>{document.querySelector('#modalPdfPesquisavel').style.display='block';window.jQuery.active=0},200);document.querySelector('#tbDocumentosCadastradas')")
            html += """<div id="modalPdfPesquisavel" style="display:none;position:fixed;inset:0;background:white;z-index:100">
                Aviso PDF pesquisável<button class="close" data-dismiss="modal" aria-label="Close" onclick="this.parentElement.style.display='none';window.noticeClosed=true">X</button></div>"""
            page.set_content(html);Robo(page,on_stage=stages.append).documents(pdf)
            self.assertTrue(page.evaluate('window.noticeClosed'))
            self.assertFalse(page.locator('#modalPdfPesquisavel').is_visible())
            self.assertIn('Documentos — fechar aviso sobre PDF pesquisável',stages)
            browser.close()

    def test_closes_notice_that_appears_during_finalize_click(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page();stages=[]
            page.route('**/confirm',lambda route:route.fulfill(content_type='text/html',body=fixture('confirm')))
            page.goto('https://local.test/confirm')
            page.set_content("""<button id="btnSalvar" onpointerover="if(!window.noticeShown){window.noticeShown=true;document.querySelector('#modalPdfPesquisavel').style.display='block';document.querySelector('.modal-backdrop').style.display='block'}" onclick="document.querySelector('iframe').src='/confirm'">Finalizar</button><iframe></iframe>
                <div class="modal-backdrop" style="display:none;position:fixed;inset:0;z-index:10;background:gray"></div>
                <div id="modalPdfPesquisavel" style="display:none;position:fixed;inset:0;z-index:20;background:white">
                PDF pesquisável<button class="close" data-dismiss="modal" aria-label="Close" onclick="this.parentElement.style.display='none';setTimeout(()=>document.querySelector('.modal-backdrop').style.display='none',150)">X</button></div>""")
            bot=Robo(page,on_stage=stages.append)
            self.assertTrue(bot.confirmation().is_visible())
            self.assertIn('Documentos — fechar aviso sobre PDF pesquisável',stages)
            self.assertFalse(page.locator('.modal-backdrop').is_visible())
            browser.close()

    def test_document_upload_waits_for_server_acknowledgment(self):
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            pdf=Path(folder)/'peticao.pdf';pdf.write_bytes(b'%PDF-1.4\n')
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page();stages=[]
            html=fixture('docs').replace('<input type="file">',"""<input type="hidden" id="fleArquivo_1"><input type="hidden" id="hdnArquivosSendoEnviados">
                <input type="file" onchange="document.querySelector('#hdnArquivosSendoEnviados').value='upload;';setTimeout(()=>{document.querySelector('#fleArquivo_1').value='server-peticao.pdf';document.querySelector('#hdnArquivosSendoEnviados').value=''},900)">""")
            html=html.replace("onclick=\"document.querySelector('#tbDocumentosCadastradas')", "onclick=\"if(!document.querySelector('#fleArquivo_1').value){alert('Documento 1 não informado.');return;}document.querySelector('#tbDocumentosCadastradas')")
            page.set_content(html);bot=Robo(page,on_stage=stages.append);bot.documents(pdf)
            self.assertIn('Documentos — aguardar conclusão do upload',stages)
            self.assertEqual(bot.alerts,[])
            self.assertIn('peticao.pdf',page.locator('#tbDocumentosCadastradas').inner_text())
            browser.close()

    def test_aborts_failed_petition_with_cancellation_confirmation(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            page.route('**/menu',lambda route:route.fulfill(content_type='text/html',body=fixture('menu')))
            page.goto('https://local.test/menu')
            page.set_content("""<input id="txtTipo_1"><button id="btnCancelar" onclick="if(confirm('Deseja cancelar o peticionamento?')) location.href='/menu'">Cancelar</button>""")
            bot=Robo(page);bot.alerts=['Documento 1 não informado.'];bot.abort_petition()
            self.assertEqual(bot.alerts,[])
            self.assertFalse(page.locator('#txtTipo_1').count())
            self.assertTrue(page.locator('#sidebar-searchbox').is_visible())
            self.assertFalse(bot.canceling)
            browser.close()

    def test_confirms_masked_cnpj_by_consulted_name_and_person_id(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            page.route('**/passive',lambda route:route.fulfill(content_type='text/html',body=fixture('passive')))
            page.goto('https://local.test/passive')
            template="""<select id="selTipoPessoa"><option value="PJ">Pessoa Jurídica</option></select>
                <input id="txtCpfCnpj"><button id="btnConsultar">Consultar</button>
                <table id="tblResultadosBusca"><thead><tr><th>Pessoa</th><th>CPF / CNPJ</th><th>Nome / Razão Social</th><th>Principal</th><th>Ações</th></tr></thead>
                <tbody><tr><td>Jurídica</td><td>90.400.888/0001-42</td><td>BANCO SANTANDER (BRASIL) S.A.</td><td><select id="selPrincipal0"><option value="S">Sim</option></select></td>
                <td><button onclick="incluirParte('PJ','123','0')">Incluir</button></td></tr></tbody></table>
                <table id="tblPartes"><thead><tr><th>id_pessoa</th><th>Nome</th><th>CPF / CNPJ</th><th>Principal?</th></tr></thead><tbody></tbody></table>
                <button id="btnProxima" onclick="location.href='/passive'">Próxima</button>
                <script>function incluirParte(){document.querySelector('#tblPartes tbody').innerHTML='<tr><td style="display:none">PERSON_ID</td><td>PARTY_NAME</td><td>0142**********</td><td><button class="btn-sin-principal">Sim</button></td></tr>';}</script>"""
            record={'TIPO_PARTE_ATIVA':'Pessoa Jurídica','CPF_CNPJ_ATIVA':'90400888000142','CLASSE_PROCESSUAL':'OUTRA CLASSE','JUSTICA_GRATUITA':''}
            for name,person_id,valid in [('BANCO SANTANDER (BRASIL) S.A.','123',True),('OUTRA EMPRESA','123',False),('BANCO SANTANDER (BRASIL) S.A.','999',False)]:
                with self.subTest(name=name,person_id=person_id):
                    page.set_content(template.replace('PARTY_NAME',name).replace('PERSON_ID',person_id))
                    bot=Robo(page)
                    if valid:
                        bot.party(record,'ATIVA')
                        self.assertTrue(page.locator('#tblResultadosBusca').is_visible())
                    else:
                        original_wait=bot.wait
                        bot.wait=lambda condition,message,timeout=60:original_wait(condition,message,timeout=.3)
                        with self.assertRaisesRegex(TimeoutError,'Parte não confirmada'):bot.party(record,'ATIVA')
            browser.close()

    def test_cnpj_waits_for_person_type_and_uses_keyboard(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            for side in ['ATIVA','PASSIVA']:
                with self.subTest(side=side):
                    page=browser.new_page();stages=[]
                    page.route('**/*',lambda route:route.fulfill(content_type='text/html',body=fixture(route.request.url.split('/')[-1])))
                    page.goto('https://local.test/active')
                    html=fixture('active').replace('012.345.678-90','05.349.595/0001-09')
                    html=html.replace('<option value="PF">','<option value="PJ">Pessoa Jurídica</option><option value="PF">',1)
                    html=html.replace('<select id="selTipoPessoa">',"<select id=\"selTipoPessoa\" onchange=\"document.querySelector('#txtCpfCnpj').disabled=true;setTimeout(()=>{document.querySelector('#txtCpfCnpj').value='';document.querySelector('#txtCpfCnpj').disabled=false;document.querySelector('#lblCpfCnpj').innerText='CNPJ:'},150)\">")
                    html=html.replace('<input id="txtCpfCnpj">','<label id="lblCpfCnpj">CPF:</label><input id="txtCpfCnpj" onkeypress="window.keypresses=(window.keypresses||0)+1">')
                    html=html.replace('location.href=\'/passive\'','location.href=\'/'+('passive' if side=='ATIVA' else 'docs')+'\'')
                    page.set_content(html)
                    record={'TIPO_PARTE_'+side:'Pessoa Jurídica','CPF_CNPJ_'+side:'05349595000109','CLASSE_PROCESSUAL':'OUTRA CLASSE','JUSTICA_GRATUITA':''}
                    Robo(page,on_stage=stages.append).party(record,side)
                    self.assertIn(('Polo ativo' if side=='ATIVA' else 'Polo passivo')+' — consultar CNPJ',stages)
                    self.assertTrue(page.url.endswith('/'+('passive' if side=='ATIVA' else 'docs')))
                    page.close()
            browser.close()

    def test_reuses_existing_petition_and_finalizes_without_upload(self):
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            pdf=Path(folder)/'peticao.pdf';pdf.write_bytes(b'%PDF-1.4\n')
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page();stages=[]
            page.route('**/confirm',lambda route:route.fulfill(content_type='text/html',body=fixture('confirm')))
            page.goto('https://local.test/confirm')
            page.set_content(f'<table id="tbDocumentosCadastradas"><tbody><tr><td><a href="acessar_documento">peticao.pdf</a></td><td>{pdf.stat().st_size} bytes</td><td>INIC</td></tr></tbody></table><button id="btnSalvar" onclick="document.querySelector(\'iframe\').src=\'/confirm\'">Finalizar</button><iframe></iframe>')
            bot=Robo(page,on_stage=stages.append);bot.documents(pdf)
            self.assertIn('Documentos — reutilizar petição já anexada; seguir para finalizar',stages)
            self.assertEqual(page.locator('#tbDocumentosCadastradas tr').count(),1)
            self.assertTrue(bot.confirmation().is_visible())
            browser.close()

    def test_rejects_different_existing_petition(self):
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            pdf=Path(folder)/'peticao.pdf';pdf.write_bytes(b'%PDF-1.4\n')
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            for name,size,kind in [('outro.pdf',9,'INIC'),('peticao.pdf',100,'INIC'),('peticao.pdf',9,'ANEXO')]:
                with self.subTest(name=name,size=size,kind=kind):
                    page.set_content(f'<table id="tbDocumentosCadastradas"><tr><td><a href="acessar_documento">{name}</a></td><td>{size} bytes</td><td>{kind}</td></tr></table>')
                    with self.assertRaises(RuntimeError):Robo(page).documents(pdf)
            browser.close()

    def test_waits_for_internal_principal_subject(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            page.set_content('<input id="hdnIdAssuntoPrincipal" value=""><table id="tblAssuntoPrincipal"><tbody><tr><td>82401842</td><td>Sim</td><td>0219032307 - Despejo</td><td>Mandado</td><td></td><td>0219032307</td></tr></tbody></table>')
            bot=Robo(page)
            with self.assertRaisesRegex(TimeoutError,'identificador interno'):
                bot.verify_principal_subject('0219032307',timeout=.3)
            page.evaluate("setTimeout(()=>document.querySelector('#hdnIdAssuntoPrincipal').value='82401842',200)")
            bot.verify_principal_subject('0219032307',timeout=2)
            browser.close()

    def test_summary_reports_eproc_missing_subject_error(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            page.set_content('<button id="btnSalvar">Finalizar</button><p>Falha no processamento da solicitação. getStrDesAssunto() on null</p>')
            with self.assertRaisesRegex(RuntimeError,'assunto principal não encontrado'):
                Robo(page).confirmation()
            browser.close()

    def test_closes_pdf_notice_before_finalizing(self):
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            pdf=Path(folder)/'peticao.pdf'; pdf.write_bytes(b'%PDF-1.4\n')
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page(); stages=[]
            page.route('**/confirm',lambda route:route.fulfill(content_type='text/html',body=fixture('confirm')))
            page.goto('https://local.test/confirm')
            html=fixture('docs').replace("onclick=\"document.querySelector('#tbDocumentosCadastradas')", "onclick=\"document.querySelector('#modalPdfPesquisavel').style.display='block';document.querySelector('#tbDocumentosCadastradas')")
            html += """<div id="modalPdfPesquisavel" style="display:none;position:fixed;inset:0;background:white;z-index:9999">
                Recomendamos PDFs pesquisáveis
                <button class="close" data-dismiss="modal" aria-label="Close" onclick="this.parentElement.style.display='none';window.noticeClosed=true">X</button></div>"""
            page.set_content(html)
            bot=Robo(page,on_stage=stages.append);bot.documents(pdf)
            self.assertTrue(page.evaluate('window.noticeClosed'))
            self.assertFalse(page.locator('#modalPdfPesquisavel').is_visible())
            self.assertIn('Documentos — fechar aviso sobre PDF pesquisável',stages)
            self.assertTrue(bot.confirmation().is_visible())
            browser.close()

    def test_document_type_keyboard_and_automatic_resolution(self):
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            pdf=Path(folder)/'peticao.pdf'; pdf.write_bytes(b'%PDF-1.4\n')
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page(); stages=[]
            html=fixture('docs').replace('oninput=', 'onkeyup=')
            html=html.replace("document.querySelector('#divInfraAjaxtxtTipo_1').style.display='block'",
                "if(this.value==='PETIÇÃO INICIAL') document.querySelector('#selTipoArquivo_1').value='1'")
            page.set_content(html)
            Robo(page,on_stage=stages.append).documents(pdf)
            self.assertIn('peticao.pdf',page.locator('#tbDocumentosCadastradas').inner_text())
            self.assertIn('Documentos — confirmar seleção de documentos',stages)
            self.assertEqual(page.locator('#selTipoArquivo_1').input_value(),'1')
            browser.close()

    def test_full_flow_with_origin_upload_and_iframe_confirmation(self):
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            pdf = Path(folder) / 'peticao.pdf'; pdf.write_bytes(b'%PDF-1.4\n')
            browser = pw.chromium.launch(headless=True, executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page = browser.new_page()
            page.route('**/*', lambda route: route.fulfill(content_type='text/html; charset=utf-8', body=HEADER + fixture(route.request.url.split('/')[-1] or 'menu')))
            record = {'CLASSE_PROCESSUAL':'MANDADO DE SEGURANÇA CÍVEL', 'PROCESSO_ORIGINARIO':'0000000-00.2026.8.26.0000',
                      'CODIGO_ASSUNTO':'0219032307','NOME_ASSUNTO':'Despejo', 'TIPO_PARTE_ATIVA':'Pessoa Física',
                      'CPF_CNPJ_ATIVA':'01234567890','JUSTICA_GRATUITA':'Requerida','TIPO_PARTE_PASSIVA':'Entidade'}
            bot = Robo(page)
            page.goto('https://eproc-2g-sp-hml.tjsp.jus.br/')
            bot.start(); bot.information(record); bot.subjects(record)
            bot.party(record,'ATIVA'); bot.party(record,'PASSIVA'); bot.documents(pdf)
            button = bot.confirmation(); button.click()
            frame, number, judge = bot.result()
            self.assertEqual(number, '4009866-56.2026.8.26.0000')
            self.assertIn('Magistrado Teste', judge)
            frame.locator('#btnFechar').click()
            self.assertTrue(page.url.endswith('/menu'))
            browser.close()

    def test_includes_subject_using_result_icon(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page(); stages=[]; actions=[]
            page.route('**/active',lambda route:route.fulfill(content_type='text/html',body='<select id="selTipoPessoa"></select>'))
            page.goto('https://local.test/active')
            page.set_content(fixture('subjects'))
            page.expose_function('recordAction',lambda name,value:actions.append((name,value)))
            page.evaluate("""() => document.addEventListener('click', e => {
                if(e.target.id==='0219032307_anchor' || e.target.id==='imgIncluir0219032307')
                    window.recordAction(e.target.id,document.querySelector('#txtDesAssunto').value);
            })""")
            Robo(page,on_stage=stages.append).subjects({'CODIGO_ASSUNTO':'0219032307','NOME_ASSUNTO':'Despejo'})
            self.assertEqual(actions,[('0219032307_anchor',''),('imgIncluir0219032307','')])
            self.assertTrue(page.locator('#selTipoPessoa').is_visible())
            self.assertIn('Assuntos — clicar no ícone Incluir assunto',stages)
            browser.close()

    def test_filter_waits_for_initialization_and_keyboard_events(self):
        self.exercise_filter(1)

    def test_filter_retries_once_if_first_search_has_no_result(self):
        self.exercise_filter(2)

    def exercise_filter(self, attempts):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            page.route('**/active',lambda route:route.fulfill(content_type='text/html',body='<select id="selTipoPessoa"></select>'))
            page.goto('https://local.test/active')
            page.set_content('''<label><input type="radio" name="mode">Assunto</label>
            <input id="txtFiltroPesquisa" onkeyup="window.typed=this.value" onchange="window.committed=true">
            <button id="btnFiltrar" onclick="acaoConsultar('filtrar')">Filtrar</button>
            <div id="divArvore" aria-busy="true"></div><input id="txtDesAssunto">
            <input id="hdnIdAssuntoPrincipal" type="hidden" value="82401842"><table id="tblAssuntoPrincipal"></table><select id="selNumCodCompetencia"><option>Direito Privado</option></select>
            <img alt="Incluir assunto" id="imgIncluir0219032307" onclick="document.querySelector('#tblAssuntoPrincipal').innerHTML='<tr><td>0219032307</td></tr>'">
            <button id="sbmProcessoEtapa2" onclick="location.href='/active'">Próxima</button>
            <script>setTimeout(()=>{
              window.acaoConsultar=()=>{
                if(window.typed==='0219032307' && window.committed){
                  document.querySelector('#divArvore').innerHTML='<a id="0219032307_anchor" >Despejo</a>';
                }
              };
              document.querySelector('#divArvore').setAttribute('aria-busy','false');
            },300);</script>'''.replace("if(window.typed===", "if((window.attempts=(window.attempts||0)+1)>="+str(attempts)+" && window.typed==="))
            # Substituir o handler da âncora por listener evita escapes no HTML aninhado da fixture.
            page.evaluate("""() => {document.addEventListener('click',e=>{if(e.target.id==='0219032307_anchor') document.querySelector('#txtDesAssunto').value='Despejo';});}""")
            bot=Robo(page); bot.subjects({'CODIGO_ASSUNTO':'0219032307','NOME_ASSUNTO':'Despejo'})
            self.assertTrue(page.locator('#selTipoPessoa').is_visible())
            browser.close()

    def test_name_fallback_handles_no_results_alert(self):
        self.exercise_name_fallback(ambiguous=False)

    def test_name_fallback_rejects_ambiguous_results(self):
        self.exercise_name_fallback(ambiguous=True)

    def exercise_name_fallback(self, ambiguous):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            page.route('**/active',lambda route:route.fulfill(content_type='text/html',body='<select id="selTipoPessoa"></select>'))
            page.goto('https://local.test/active')
            page.set_content('''<label><input type="radio" name="mode">Assunto</label>
            <input id="txtFiltroPesquisa"><button id="btnFiltrar" onclick="filter()">Filtrar</button>
            <div id="divArvore"></div><input id="txtDesAssunto"><input id="hdnIdAssuntoPrincipal" type="hidden" value="82401842"><table id="tblAssuntoPrincipal"></table>
            <select id="selNumCodCompetencia"><option>Direito Privado</option></select>
            <img alt="Incluir assunto" id="imgIncluir0219032307" onclick="document.querySelector('#tblAssuntoPrincipal').innerHTML='<tr><td>0219032307 - Despejo por Inadimplemento</td></tr>'">
            <button id="sbmProcessoEtapa2" onclick="location.href='/active'">Próxima</button>
            <script>function filter(){
              const query=document.querySelector('#txtFiltroPesquisa').value;
              if(query==='9999999999'){alert('Não foram encontrados registros com sua busca, tente outros termos');return;}
              document.querySelector('#divArvore').innerHTML='<a class="jstree-anchor" id="0219032307_anchor">Despejo por Inadimplemento (0219032307)</a>';
              if(window.ambiguous) document.querySelector('#divArvore').innerHTML+='<a class="jstree-anchor" id="99998888_anchor">Despejo por Inadimplemento (99998888)</a>';
            }
            document.addEventListener('click',e=>{if(e.target.classList.contains('jstree-anchor')) document.querySelector('#txtDesAssunto').value=e.target.textContent;});
            </script>''')
            page.evaluate('(value)=>{window.ambiguous=value}',ambiguous)
            bot=Robo(page)
            record={'CODIGO_ASSUNTO':'9999999999','NOME_ASSUNTO':'DESPEJO POR INADIMPLEMENTO'}
            if ambiguous:
                with self.assertRaisesRegex(RuntimeError,'ambígua'): bot.subjects(record)
                self.assertEqual(page.locator('#tblAssuntoPrincipal tr').count(),0)
            else:
                bot.subjects(record)
                self.assertTrue(page.locator('#selTipoPessoa').is_visible())
            browser.close()

    def test_login_accepts_direct_panel_without_profile_screen(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page()
            def route(request):
                if request.request.url.endswith('/logged'):
                    body='<input id="sidebar-searchbox">'
                else:
                    body='<input id="username"><input id="password"><button id="kc-login" onclick="location.href=\'/logged\'">Entrar</button>'
                request.fulfill(content_type='text/html',body=body)
            page.route('**/*',route)
            bot=Robo(page); bot.login('usuario-fixture','senha-fixture')
            self.assertTrue(page.locator('#sidebar-searchbox').is_visible())
            browser.close()

    def test_start_uses_authenticated_menu_without_revisiting_login(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page(); requests=[]
            def route(request):
                requests.append(request.request.url)
                request.fulfill(content_type='text/html',body='<select id="selLocalidadeJudicial"><option>Tribunal</option></select>')
            page.route('**/*',route)
            page.goto('https://eproc-2g-sp-hml.tjsp.jus.br/controlador.php?acao=principal')
            requests.clear()
            page.set_content('<input id="sidebar-searchbox"><a aria-label="Petição Inicial" href="controlador.php?acao=processo_cadastrar">Petição Inicial</a>')
            Robo(page).start()
            self.assertEqual(len(requests),1)
            self.assertIn('acao=processo_cadastrar',requests[0])
            browser.close()

    def test_entity_suggestion_with_cnpj_suffix_is_selected_before_include(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page();stages=[]
            page.route('**/docs',lambda route:route.fulfill(content_type='text/html',body='<input id="txtTipo_1">'))
            page.goto('https://local.test/docs')
            page.set_content("""<select id="selTipoPessoa"><option value="ENT">Entidade</option></select>
                <input id="hdnIdEntidade" type="hidden"><input id="txtEntidade" onkeyup="document.querySelector('.infraAjaxAutoCompletar').style.display='block'">
                <div class="infraAjaxAutoCompletar" style="display:none">
                <a onclick="document.querySelector('#hdnIdEntidade').value='wrong'">CAIXA CONSORCIOS S.A. ADMINISTRADORA DE CONSORCIOS (CNPJ: 00.000.000/0001-91)</a>
                <a onclick="document.querySelector('#hdnIdEntidade').value='correct';document.querySelector('#btnIncluirEnt').disabled=false;this.parentElement.style.display='none'">CAIXA CONSORCIOS S.A. ADMINISTRADORA DE CONSORCIOS (CNPJ: 05.349.595/0001-09)</a></div>
                <select id="selPrincipalEnt"><option value="S">Sim</option></select>
                <button id="btnIncluirEnt" disabled onclick="if(document.querySelector('#hdnIdEntidade').value==='correct') document.querySelector('#tblPartes tbody').innerHTML='<tr><td>CAIXA CONSORCIOS S.A. ADMINISTRADORA DE CONSORCIOS</td><td><button class=btn-sin-principal>Sim</button></td></tr>'">Incluir</button>
                <table id="tblPartes"><tbody></tbody></table><button id="btnProxima" onclick="location.href='/docs'">Próxima</button>""")
            Robo(page,on_stage=stages.append).party({'CLASSE_PROCESSUAL':'OUTRA CLASSE','TIPO_PARTE_PASSIVA':'Entidade','NOME_ENTIDADE_PASSIVA':'CAIXA CONSORCIOS S.A. ADMINISTRADORA DE CONSORCIOS','CPF_CNPJ_PASSIVA':'05349595000109'},'PASSIVA')
            self.assertIn('Polo passivo — selecionar entidade cadastrada',stages)
            self.assertTrue(page.locator('#txtTipo_1').is_visible())
            browser.close()

    def test_entity_autocomplete_and_principal(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, executable_path=os.environ.get('EPROC_TEST_CHROMIUM')); page = browser.new_page()
            page.route('**/docs', lambda route: route.fulfill(content_type='text/html', body='<input id="txtTipo_1">'))
            page.goto('https://local.test/docs')
            page.set_content('''<select id="selTipoPessoa"><option value="ENT">Entidade</option></select>
              <input id="txtEntidade" onkeyup="document.querySelector('.infraAjaxAutoCompletar').style.display='block'">
              <div class="infraAjaxAutoCompletar" style="display:none"><a onclick="this.parentElement.style.display='none'">ENTIDADE TESTE</a></div>
              <select id="selPrincipalEnt"><option value="N">Não</option><option value="S">Sim</option></select>
              <button id="btnIncluirEnt" onclick="document.querySelector('#tblPartes tbody').innerHTML='<tr><td>ENTIDADE TESTE</td><td><button class=btn-sin-principal>Sim</button></td></tr>'">Incluir</button>
              <table id="tblPartes"><tbody></tbody></table><button id="btnProxima" onclick="location.href='/docs'">Próxima</button>''')
            bot = Robo(page)
            bot.party({'CLASSE_PROCESSUAL':'PROCEDIMENTO COMUM CÍVEL','TIPO_PARTE_PASSIVA':'Entidade',
                       'NOME_ENTIDADE_PASSIVA':'ENTIDADE TESTE'}, 'PASSIVA')
            self.assertTrue(page.locator('#txtTipo_1').is_visible())
            browser.close()

    def test_entity_resolved_without_open_suggestions_clicks_include(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('EPROC_TEST_CHROMIUM'))
            page=browser.new_page();stages=[]
            page.route('**/docs',lambda route:route.fulfill(content_type='text/html',body='<input id="txtTipo_1">'))
            page.goto('https://local.test/docs')
            page.set_content("""<select id="selTipoPessoa"><option value="ENT">Entidade</option></select>
                <input id="hdnIdEntidade" type="hidden"><input id="txtEntidade"
                onkeyup="if(this.value==='ENTIDADE TESTE') document.querySelector('#hdnIdEntidade').value='123'"
                onblur="if(document.querySelector('#hdnIdEntidade').value) {document.querySelector('#btnIncluirEnt').style.display='block';document.querySelector('#selPrincipalEnt').style.display='block'}">
                <select id="selPrincipalEnt" style="display:none"><option value="N">Não</option><option value="S">Sim</option></select>
                <button id="btnIncluirEnt" style="display:none" onclick="document.querySelector('#tblPartes tbody').innerHTML='<tr><td>ENTIDADE TESTE</td><td><button class=btn-sin-principal>Sim</button></td></tr>'">Incluir</button>
                <table id="tblPartes"><tbody></tbody></table><button id="btnProxima" onclick="location.href='/docs'">Próxima</button>""")
            Robo(page,on_stage=stages.append).party({'CLASSE_PROCESSUAL':'OUTRA CLASSE','TIPO_PARTE_PASSIVA':'Entidade','NOME_ENTIDADE_PASSIVA':'ENTIDADE TESTE'},'PASSIVA')
            self.assertIn('Polo passivo — clicar em Incluir entidade',stages)
            self.assertTrue(page.locator('#txtTipo_1').is_visible())
            browser.close()

    def test_alert_is_failure_and_never_accepted(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, executable_path=os.environ.get('EPROC_TEST_CHROMIUM')); page = browser.new_page(); bot = Robo(page)
            page.set_content('<button onclick="alert(\'Não foram encontrados registros\')">Filtrar</button>')
            page.locator('button').click()
            with self.assertRaisesRegex(RuntimeError, 'Não foram encontrados'):
                bot.wait(lambda: False, 'Sem resultado', timeout=1)
            browser.close()

if __name__ == '__main__': unittest.main()
