"""Automação do fluxo de homologação EPROC TJSP 2G para Windows."""
import argparse
import getpass
import re
import time
import unicodedata
from pathlib import Path
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError
from controle import Controle, digits, validate

URL = 'https://eproc-2g-sp-hml.tjsp.jus.br/'
MP = 'MINISTÉRIO PÚBLICO DO ESTADO DE SÃO PAULO'


class SubjectNotFound(RuntimeError):
    pass

class SubjectCompetenceError(RuntimeError):
    pass

def normalized_subject(text):
    plain = unicodedata.normalize('NFKD', text)
    return ' '.join(''.join(c for c in plain if not unicodedata.combining(c)).casefold().split())

class Robo:
    def __init__(self, page, sigilo=None, on_stage=None):
        self.page = page
        self.sigilo = sigilo
        self.on_stage = on_stage
        self.stage = 'Início'
        self.alerts = []
        self.submitted = False
        self.canceling = False
        page.on('dialog', self.dialog)

    @property
    def stage(self):
        return self._stage

    @stage.setter
    def stage(self, value):
        self._stage = value
        if self.on_stage:
            self.on_stage(value)

    def dialog(self, dialog):
        if self.canceling and dialog.type == 'confirm':
            dialog.accept()
            return
        # Não confirmar automaticamente diálogos inesperados de submissão.
        self.alerts.append(dialog.message)
        dialog.dismiss()

    def wait(self, condition, message, timeout=60):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.page.is_closed():
                raise RuntimeError('A aba controlada pelo robô foi fechada durante: ' + self.stage)
            if self.alerts:
                raise RuntimeError('Aviso do sistema: ' + self.alerts.pop(0))
            if self.stage.startswith('Assuntos'):
                self.check_subject_competence_error()
            value = condition()
            if value:
                return value
            self.page.wait_for_timeout(100)
        raise TimeoutError(message)

    def visible(self, selector):
        return self.page.locator(selector).filter(visible=True).first

    def click(self, selector):
        self.visible(selector).click()

    def abort_petition(self):
        if self.submitted:
            raise RuntimeError('Não será cancelado um peticionamento com protocolo já enviado.')
        self.stage = 'Recuperação — cancelar peticionamento com erro'
        self.alerts.clear()
        self.close_pdf_notice()
        # Cancelar pode retornar à etapa inicial, mantendo outro formulário na página.
        # A confirmação deve observar a etapa que falhou, não todos os campos do fluxo.
        step_selector = next((selector for selector in
                              ['#txtTipo_1', '#tblPartes', '#txtFiltroPesquisa', '#selLocalidadeJudicial']
                              if self.page.locator(selector).is_visible()), None)
        if not step_selector:
            return
        def cancelled():
            if not self.page.locator(step_selector).is_visible():
                return True
            if step_selector == '#selLocalidadeJudicial':
                selected_class = self.page.locator('#selIdClasseJudicial')
                return selected_class.count() == 1 and selected_class.input_value() in ['', 'null']
            return False
        cancel = self.visible('#btnCancelar')
        if not cancel.count():
            raise RuntimeError('Botão Cancelar não encontrado; não foi possível encerrar o rascunho com erro.')
        self.canceling = True
        try:
            cancel.click()
            self.wait(cancelled, 'O EPROC não confirmou o cancelamento do rascunho.', timeout=15)
            self.stage = 'Recuperação — rascunho encerrado; pronto para a próxima linha'
        finally:
            self.canceling = False

    def login(self, user, password):
        self.stage = 'Login — abrir página'
        self.page.goto(URL)
        self.stage = 'Login — preencher credenciais'
        self.page.locator('#username').fill(user)
        # Digitação real respeita o componente MaskedPassword observado no HTML.
        self.page.locator('#password').press_sequentially(password, delay=80)
        self.stage = 'Login — clicar em Entrar'
        self.click('#kc-login')
        self.stage = 'Login — aguardar perfil ou painel'
        def destination():
            if self.page.locator('button[data-descricao="ADVOGADO"]').is_visible():
                return 'perfil'
            if self.page.locator('#sidebar-searchbox').count():
                return 'painel'
            feedback = self.page.locator('#input-error, #input-error-username, .kc-feedback-text').filter(visible=True)
            if feedback.count() and feedback.first.inner_text().strip():
                raise RuntimeError('Resposta do login: ' + feedback.first.inner_text().strip())
            return None
        if self.wait(destination, 'Login não chegou à seleção de perfil nem ao painel do advogado.') == 'perfil':
            self.stage = 'Login — selecionar ADVOGADO'
            self.click('button[data-descricao="ADVOGADO"]')
        self.stage = 'Login — aguardar menu do advogado'
        self.page.locator('#sidebar-searchbox').wait_for(state='attached')

    def start(self):
        self.stage = 'Menu / nova petição'
        if self.page.locator('#username').is_visible():
            raise RuntimeError('Sessão expirada: reinicie o robô para autenticar.')
        search = self.page.locator('#sidebar-searchbox')
        if not search.count():
            home = self.page.locator('#btn-home, a[aria-label="Voltar para o Painel Inicial"]').filter(visible=True).first
            if not home.count():
                raise RuntimeError('Menu do advogado não encontrado na sessão atual. Não será efetuado novo login automático.')
            home.click()
            search.wait_for(state='attached')
        if not search.is_visible():
            self.click('#menu-btn')
        search.fill('petição inicial')
        self.click('a[aria-label="Petição Inicial"]')
        self.page.locator('#selLocalidadeJudicial').wait_for()

    def information(self, record):
        self.stage = 'Informações do processo'
        expect(self.page.locator('#selLocalidadeJudicial')).to_have_value('400')
        pred = self.page.locator('#btnPredicao')
        if pred.is_visible():
            pred.set_checked(False)
        self.page.locator('#selIdGrupoCompetencia').select_option(label='Direito Privado')
        self.wait(lambda: record['CLASSE_PROCESSUAL'] in self.page.locator('#selIdClasseJudicial option').all_text_contents(),
                  'Classe não carregada para Direito Privado.')
        with self.page.expect_navigation(wait_until='domcontentloaded'):
            self.page.locator('#selIdClasseJudicial').select_option(label=record['CLASSE_PROCESSUAL'])
        origin = record['PROCESSO_ORIGINARIO']
        if origin:
            self.page.locator('#txtProcessoOriginario').wait_for()
            expect(self.page.locator('#selTipoJustica')).to_have_value('1')
            self.page.locator('#txtProcessoOriginario').fill(origin)
            self.page.locator('#txtProcessoOriginario').press('Tab')
            self.wait(lambda: self.page.locator('#txtDescJuizo').input_value().strip(), 'Juízo não carregado.')
        plantao = self.page.locator('#chkRemeterPlantao')
        if plantao.is_visible():
            plantao.set_checked(False)
        # Algumas classes, como PETIÇÃO CÍVEL, não exibem valor da causa.
        no_value = self.page.locator('#chkNaoAplicaValor')
        if no_value.is_visible():
            no_value.set_checked(True)
        self.click('#btnSalvar')
        self.page.locator('#txtFiltroPesquisa').wait_for()

    def subject_search_ready(self):
        return self.page.evaluate("""() => {
            const field = document.getElementById('txtFiltroPesquisa');
            const button = document.getElementById('btnFiltrar');
            const tree = document.getElementById('divArvore');
            if (!field || !button || !tree || button.disabled || tree.getAttribute('aria-busy') === 'true') return false;
            const handler = button.getAttribute('onclick') || '';
            if (handler.includes('acaoConsultar') && typeof acaoConsultar !== 'function') return false;
            if (window.jQuery && window.jQuery.fn.jstree) {
                const instance = window.jQuery(tree).jstree(true);
                if (!instance || (instance._data && instance._data.core && instance._data.core.ready === false)) return false;
            }
            return true;
        }""")

    def matching_subjects(self, code='', name='', code_hint=''):
        tree = self.page.locator('#divArvore')
        if code:
            target = tree.locator('[id="' + code + '_anchor"]').filter(visible=True)
            return target.all()
        expected = normalized_subject(name)
        matches = []
        for candidate in tree.locator('a.jstree-anchor').filter(visible=True).all():
            description = re.sub(r'\s*\(\d+\)\s*$', '', candidate.inner_text()).strip()
            if normalized_subject(description) == expected:
                matches.append(candidate)
        if len(matches) > 1 and code_hint:
            exact = [item for item in matches if item.get_attribute('id') == code_hint + '_anchor']
            if len(exact) == 1:
                return exact
        return matches

    def filter_subject(self, query, code='', name='', code_hint=''):
        mode = 'código' if code else 'nome'
        self.stage = 'Assuntos — preencher ' + mode
        field = self.page.locator('#txtFiltroPesquisa')
        field.fill('')
        field.press_sequentially(query, delay=35)
        expect(field).to_have_value(query)
        field.press('Tab')
        for attempt in range(1, 3):
            self.wait(self.subject_search_ready, 'A busca de assuntos continua ocupada.')
            self.stage = f'Assuntos — Filtrar por {mode} (tentativa {attempt}/2)'
            self.click('#btnFiltrar')
            self.stage = 'Assuntos — aguardar resultado por ' + mode
            try:
                result = self.wait(lambda: self.matching_subjects(code, name, code_hint),
                                   'Nenhum assunto correspondente à busca por ' + mode, timeout=15)
            except TimeoutError:
                if attempt == 1:
                    continue
                raise SubjectNotFound('Nenhum assunto correspondente após buscar por ' + mode + ': ' + query)
            except RuntimeError as error:
                if 'não foram encontrados registros' in str(error).casefold():
                    raise SubjectNotFound('O EPROC não encontrou registros por ' + mode + ': ' + query) from error
                raise
            if len(result) != 1:
                raise RuntimeError('Busca de assunto ambígua: vários resultados com o mesmo nome. Confira código e nome na planilha.')
            return result[0]
        raise SubjectNotFound('Assunto não encontrado.')

    def check_subject_competence_error(self):
        warning = self.page.get_by_text('Não há nenhuma competência associada a este assunto principal', exact=False).filter(visible=True)
        if warning.count():
            message = warning.first.inner_text().strip()
            raise SubjectCompetenceError('Assunto sem competência na área configurada: ' + message)

    def select_private_competence(self):
        self.stage = 'Assuntos — verificar competência Direito Privado'
        self.wait(lambda: 'Direito Privado' in self.page.locator('#selNumCodCompetencia option').all_text_contents(),
                  'A competência Direito Privado não foi disponibilizada para o assunto.', timeout=15)
        self.page.locator('#selNumCodCompetencia').select_option(label='Direito Privado')

    def verify_principal_subject(self, verification, timeout=15):
        self.stage = 'Assuntos — confirmar identificador do assunto principal'
        table = self.page.locator('#tblAssuntoPrincipal')
        self.wait(lambda: table.count() and verification in table.inner_text(),
                  'Assunto não confirmado na tabela.', timeout=timeout)
        def ready():
            principal = self.page.locator('#hdnIdAssuntoPrincipal')
            if principal.count() != 1 or not principal.input_value().strip():
                return False
            rows = table.locator('tbody tr')
            if rows.count() != 1:
                return False
            cells = rows.first.locator('td')
            if cells.count() >= 6:
                if cells.nth(1).inner_text().strip() != 'Sim':
                    return False
                if cells.first.inner_text().strip() != principal.input_value().strip():
                    return False
            return self.page.evaluate('() => !window.jQuery || !window.jQuery.active')
        self.wait(ready, 'O EPROC não confirmou o identificador interno do assunto principal. '
                  'A presença do texto na tabela não confirma essa gravação.', timeout=timeout)

    def subjects(self, record):
        self.stage = 'Assuntos'
        selected = self.page.locator('#tblAssuntoPrincipal')
        existing = selected.locator('tbody tr').all_inner_texts()
        if existing:
            target_value = record['CODIGO_ASSUNTO'] or record['NOME_ASSUNTO']
            if len(existing) != 1 or target_value not in existing[0]:
                raise RuntimeError('Já existe assunto diferente no peticionamento.')
            self.verify_principal_subject(target_value)
            self.select_private_competence()
            self.click('#sbmProcessoEtapa2')
            self.page.locator('#selTipoPessoa').wait_for()
            return
        self.stage = 'Assuntos — aguardar inicialização da busca'
        self.wait(self.subject_search_ready, 'A busca de assuntos não terminou de inicializar.')
        self.stage = 'Assuntos — selecionar modo Assunto'
        # Busca por assunto, nunca por glossário.
        self.page.get_by_label('Assunto', exact=True).check()
        code = record['CODIGO_ASSUNTO']
        name = record['NOME_ASSUNTO']
        try:
            target = self.filter_subject(code or name, code=code, name=name)
        except SubjectNotFound:
            if not code or not name:
                raise
            self.stage = 'Assuntos — código sem resultado; buscar pelo nome'
            target = self.filter_subject(name, name=name, code_hint=code)
        target_text = target.inner_text().strip()
        selected_code = re.search(r'\((\d+)\)\s*$', target_text)
        verification = selected_code.group(1) if selected_code else (code or name)
        self.stage = 'Assuntos — selecionar resultado'
        target.click()
        # A inclusão é feita pelo ícone do próprio resultado (incluirAssunto).
        anchor_id = target.get_attribute('id') or ''
        icon_code = anchor_id.removesuffix('_anchor')
        if not icon_code.isdigit():
            raise RuntimeError('Não foi possível identificar o ícone de inclusão do assunto.')
        self.stage = 'Assuntos — clicar no ícone Incluir assunto'
        self.page.locator(f'[id="imgIncluir{icon_code}"]').click()
        self.stage = 'Assuntos — conferir inclusão e competência'
        table = self.page.locator('#tblAssuntoPrincipal')
        self.verify_principal_subject(verification)
        self.select_private_competence()
        self.click('#sbmProcessoEtapa2')
        self.page.locator('#selTipoPessoa').wait_for()

    def matching_entity_suggestions(self, name, cnpj=''):
        name_pattern = r'\s+'.join(re.escape(part) for part in name.strip().split())
        pattern = re.compile(r'^\s*' + name_pattern + r'(?:\s*\(CNPJ:\s*[\d./-]+\))?\s*$', re.IGNORECASE)
        candidates = self.page.locator('.infraAjaxAutoCompletar').filter(visible=True).get_by_text(pattern).all()
        document = digits(cnpj)
        if document and candidates:
            with_document = [(item, re.search(r'\(CNPJ:\s*([\d./-]+)\)', item.inner_text(), re.IGNORECASE))
                             for item in candidates]
            if any(match for _, match in with_document):
                exact = [item for item, match in with_document if match and digits(match.group(1)) == document]
                if not exact:
                    raise RuntimeError('A entidade sugerida tem CNPJ diferente do informado na planilha.')
                return exact
        return candidates

    def party(self, record, side):
        self.stage = 'Polo ativo' if side == 'ATIVA' else 'Polo passivo'
        if self.page.locator('#tblPartes tbody tr').count():
            raise RuntimeError('Polo já contém parte: confira o rascunho antes de continuar.')
        kind = record['TIPO_PARTE_' + side]
        ms = side == 'PASSIVA' and record['CLASSE_PROCESSUAL'].startswith('MANDADO DE SEGURANÇA')
        table = self.page.locator('#tblResultadosBusca')
        if ms:
            self.wait(lambda: table.is_visible() and MP in table.inner_text(), 'Ministério Público não carregado.')
            identity = MP
        elif kind == 'Entidade':
            prefix = 'Polo ativo' if side == 'ATIVA' else 'Polo passivo'
            self.stage = prefix + ' — selecionar tipo Entidade'
            self.page.locator('#selTipoPessoa').select_option('ENT')
            identity = record['NOME_ENTIDADE_' + side]
            field = self.page.locator('#txtEntidade')
            self.stage = prefix + ' — buscar entidade pelo nome'
            field.fill('')
            field.press_sequentially(identity, delay=35)
            entity_id = self.page.locator('#hdnIdEntidade')
            cnpj_hint = record.get('CPF_CNPJ_' + side, '')
            def suggestions():
                return self.matching_entity_suggestions(identity, cnpj_hint)
            def resolved():
                return entity_id.count() == 1 and bool(entity_id.input_value().strip())
            self.wait(lambda: suggestions() or resolved(),
                      'O sistema não disponibilizou a entidade informada pelo nome.')
            found_entities = suggestions()
            if found_entities:
                if len(found_entities) != 1:
                    raise RuntimeError('Entidade ambígua na consulta.')
                self.stage = prefix + ' — selecionar entidade cadastrada'
                found_entities[0].click()
            field.press('Tab')
            button = self.page.locator('#btnIncluirEnt')
            self.wait(lambda: button.is_visible() and button.is_enabled()
                      and (not entity_id.count() or resolved()), 'A inclusão da entidade não ficou disponível.')
            self.visible('#selPrincipalEnt').select_option('S')
            self.stage = prefix + ' — clicar em Incluir entidade'
            button.click()
            self.stage = prefix + ' — conferir entidade na tabela'
        else:
            person_type = 'PF' if kind == 'Pessoa Física' else 'PJ'
            document_name = 'CPF' if person_type == 'PF' else 'CNPJ'
            self.stage = ('Polo ativo' if side == 'ATIVA' else 'Polo passivo') + ' — selecionar ' + kind
            self.page.locator('#selTipoPessoa').select_option(person_type)
            identity = digits(record['CPF_CNPJ_' + side])
            field = self.page.locator('#txtCpfCnpj')
            label = self.page.locator('#lblCpfCnpj')
            def ready():
                return (field.is_visible() and field.is_enabled() and field.is_editable()
                        and (not label.count() or document_name in label.inner_text().upper())
                        and self.page.evaluate('() => !window.jQuery || !window.jQuery.active'))
            self.wait(ready, 'O campo de ' + document_name + ' não ficou disponível após a seleção do tipo de pessoa.')
            self.stage = ('Polo ativo' if side == 'ATIVA' else 'Polo passivo') + ' — preencher ' + document_name
            field.fill('')
            field.press_sequentially(identity, delay=35)
            field.press('Tab')
            self.wait(lambda: digits(field.input_value()) == identity,
                      'O ' + document_name + ' preenchido não corresponde ao informado na planilha.', timeout=5)
            self.stage = ('Polo ativo' if side == 'ATIVA' else 'Polo passivo') + ' — consultar ' + document_name
            self.click('#btnConsultar')
            self.wait(lambda: table.is_visible() and any(identity in digits(r.inner_text())
                      for r in table.locator('tbody tr').all()), 'Consulta sem resultado para o ' + document_name + ' informado.')
        expected_name = None
        expected_person_id = None
        if ms or kind != 'Entidade':
            rows = table.locator('tbody tr')
            found = []
            for row in rows.all():
                text = row.inner_text()
                if (ms and identity in text) or (not ms and identity in digits(text)):
                    found.append(row)
            if len(found) != 1:
                raise RuntimeError('Consulta sem resultado único para a parte informada.')
            row = found[0]
            row.locator('select[id^="selPrincipal"]').select_option('S')
            include_button = row.locator('button').filter(has_text='Incluir')
            headers = table.locator('thead th').all_text_contents()
            for index, header in enumerate(headers):
                if normalized_subject(header).startswith('nome'):
                    expected_name = normalized_subject(row.locator('td').nth(index).inner_text())
                    break
            handler = include_button.get_attribute('onclick') or ''
            person_id = re.search(r"incluirParte\(\s*['\"](?:PF|PJ|ENT)['\"]\s*,\s*['\"]([^'\"]+)['\"]", handler)
            expected_person_id = person_id.group(1) if person_id else None
            include_button.click()
        included = self.page.locator('#tblPartes tbody tr').filter(has=self.page.locator('td'))
        def confirmed(row):
            if kind == 'Entidade' or ms:
                return identity in row.inner_text()
            headers = self.page.locator('#tblPartes thead th').all_text_contents()
            values = {}
            for index, header in enumerate(headers):
                values[normalized_subject(header)] = row.locator('td').nth(index).text_content().strip()
            document = next((v for k, v in values.items() if 'cpf' in k and 'cnpj' in k), row.inner_text())
            if '*' not in document:
                return identity == digits(document) if values else identity in digits(document)
            name = next((v for k, v in values.items() if k.startswith('nome')), '')
            if not expected_name or normalized_subject(name) != expected_name:
                return False
            included_id = values.get('id_pessoa')
            if expected_person_id and included_id:
                return included_id == expected_person_id
            return True
        self.stage = ('Polo ativo' if side == 'ATIVA' else 'Polo passivo') + ' — conferir parte incluída'
        self.wait(lambda: any(confirmed(r) for r in included.all()), 'Parte não confirmada na tabela.')
        matches = [r for r in included.all() if confirmed(r)]
        if len(matches) != 1:
            raise RuntimeError('Parte incluída não identificada de forma única.')
        expect(matches[0].locator('.btn-sin-principal')).to_have_text('Sim')
        if side == 'ATIVA' and record['JUSTICA_GRATUITA']:
            matches[0].locator('select[id^="selJusticaAutor"]').select_option(label=record['JUSTICA_GRATUITA'])
        self.click('#btnProxima')
        if side == 'ATIVA':
            self.page.locator('#tblPartes').wait_for(state='attached')
        else:
            self.page.locator('#txtTipo_1').wait_for()

    def documents(self, pdf):
        self.stage = 'Documentos'
        self.close_pdf_notice()
        table = self.page.locator('#tbDocumentosCadastradas')
        existing = table.locator('tr').filter(has=self.page.get_by_role('link'))
        if existing.count():
            self.stage = 'Documentos — conferir petição já anexada'
            if existing.count() != 1:
                raise RuntimeError('O rascunho contém mais de um documento; confira antes de finalizar.')
            row = existing.first
            if row.get_by_role('link', name=pdf.name, exact=True).count() != 1:
                raise RuntimeError('O documento do rascunho não corresponde ao PDF esperado.')
            if not re.search(r'\bINIC\b', row.inner_text()):
                raise RuntimeError('O documento do rascunho não está como Petição Inicial (INIC).')
            size = re.search(r'([1-9]\d*)\s*bytes', row.inner_text())
            if not size or int(size.group(1)) != pdf.stat().st_size:
                raise RuntimeError('O tamanho do documento do rascunho não corresponde ao PDF esperado.')
            if self.sigilo and self.sigilo not in row.inner_text():
                raise RuntimeError('O sigilo do documento do rascunho não corresponde ao configurado.')
            self.stage = 'Documentos — reutilizar petição já anexada; seguir para finalizar'
            return
        self.stage = 'Documentos — anexar arquivo'
        self.page.locator('input[type="file"]').first.set_input_files(str(pdf))
        self.stage = 'Documentos — aguardar conclusão do upload'
        uploaded_file = self.page.locator('#fleArquivo_1')
        sending = self.page.locator('#hdnArquivosSendoEnviados')
        self.wait(lambda: (not uploaded_file.count() or bool(uploaded_file.input_value().strip()))
                  and (not sending.count() or not sending.input_value().strip()),
                  'O EPROC não confirmou a conclusão do upload da petição.', timeout=120)
        self.stage = 'Documentos — selecionar tipo Petição Inicial'
        field = self.page.locator('#txtTipo_1')
        field.fill('')
        field.press_sequentially('PETIÇÃO INICIAL', delay=35)
        type_code = self.page.locator('#selTipoArquivo_1')
        suggestion = self.page.locator('#divInfraAjaxtxtTipo_1').get_by_text('PETIÇÃO INICIAL', exact=True).first
        self.wait(lambda: type_code.input_value() == '1' or suggestion.is_visible(),
                  'O sistema não disponibilizou o tipo Petição Inicial.')
        # O autocomplete pode resolver o tipo diretamente, sem manter a lista aberta.
        if type_code.input_value() != '1':
            suggestion.click()
        expect(type_code).to_have_value('1')
        field.press('Tab')
        if self.sigilo:
            self.page.locator('#selIdSigilo_1').select_option(label=self.sigilo)
        self.stage = 'Documentos — confirmar seleção de documentos'
        self.click_document_action('#btnEnviarArquivos')
        self.stage = 'Documentos — conferir arquivo na tabela'
        table = self.page.locator('#tbDocumentosCadastradas')
        row = table.locator('tr').filter(has=self.page.get_by_role('link', name=pdf.name, exact=True))
        def uploaded():
            self.close_pdf_notice()
            return (row.count() > 0 and row.first.is_visible()
                    and not self.page.locator('#aguardandoAnexaDoc').is_visible()
                    and self.page.evaluate('() => !window.jQuery || !window.jQuery.active'))
        self.wait(uploaded, 'Documento não apareceu na tabela após a confirmação.')
        if row.count() != 1:
            raise RuntimeError('Documento não identificado de forma única.')
        expect(row).to_contain_text('INIC')
        if not re.search(r'[1-9]\d*\s*bytes', row.inner_text()):
            raise RuntimeError('Tamanho do documento não confirmado.')

    def pdf_notice_controls(self):
        for frame in self.page.frames:
            # O contêiner pode ter dimensão zero enquanto o diálogo e seu X estão visíveis.
            known = frame.locator('#modalPdfPesquisavel')
            controls = known.locator('button[data-dismiss="modal"], button[data-bs-dismiss="modal"]').filter(visible=True)
            if controls.count():
                return frame, known, controls.first
            candidates = frame.locator('.modal-content').filter(has_text='Recomendamos que os arquivos PDFs enviados')
            for content in candidates.all():
                if 'pesquis' not in normalized_subject(content.inner_text()):
                    continue
                controls = content.locator('button[data-dismiss="modal"], button[data-bs-dismiss="modal"]').filter(visible=True)
                if controls.count():
                    return frame, content, controls.first
        return None

    def close_pdf_notice(self):
        notice = self.pdf_notice_controls()
        if not notice:
            return
        frame, modal, close = notice
        self.stage = 'Documentos — fechar aviso sobre PDF pesquisável'
        # Dispara o próprio botão X, sem o scroll automático do clique físico.
        close.evaluate('(button) => button.click()')
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and close.is_visible():
            self.page.wait_for_timeout(100)
        if close.is_visible():
            # Usa o ciclo de fechamento do Bootstrap, preservando limpeza do fundo e eventos.
            close.evaluate("""button => {
                const element = button.closest('.modal') || button.closest('#modalPdfPesquisavel');
                if (element && window.jQuery && typeof window.jQuery.fn.modal === 'function')
                    window.jQuery(element).modal('hide');
            }""")
        self.wait(lambda: not close.is_visible()
                  and frame.locator('.modal-backdrop').filter(visible=True).count() == 0,
                  'O aviso de PDF não foi fechado pelo botão X.', timeout=10)
        self.stage = 'Documentos — conferir arquivo na tabela'

    def click_document_action(self, selector):
        action_stage = self.stage
        def clicked():
            self.close_pdf_notice()
            self.stage = action_stage
            if any(frame.locator('.modal-backdrop').filter(visible=True).count() for frame in self.page.frames):
                return False
            try:
                self.visible(selector).click(timeout=750)
                return True
            except PlaywrightTimeoutError:
                # O aviso pode surgir durante a tentativa de clique, após a verificação.
                return False
        self.wait(clicked, 'O botão da etapa de documentos permaneceu bloqueado: ' + selector, timeout=30)

    def confirmation(self):
        self.close_pdf_notice()
        self.stage = 'Resumo do ajuizamento'
        self.click_document_action('#btnSalvar')
        def find():
            for frame in self.page.frames:
                body = frame.locator('body')
                if body.count() and 'getStrDesAssunto() on null' in body.inner_text():
                    raise RuntimeError('O EPROC falhou ao montar o resumo: assunto principal não encontrado '
                                       '(getStrDesAssunto() on null). Nenhum ajuizamento foi confirmado.')
                button = frame.locator('#sbmConfirmar')
                if button.count() and button.is_visible():
                    return button
            return None
        return self.wait(find, 'Confirmação de ajuizamento não encontrada.')

    def result(self):
        self.stage = 'Resultado do protocolo'
        def find():
            for frame in self.page.frames:
                message = frame.locator('#divDesProcessoEnviado')
                if message.count() and message.is_visible() and 'Processo distribuído' in message.inner_text():
                    return frame
            return None
        frame = self.wait(find, 'Resultado da distribuição não confirmado.', timeout=120)
        number = frame.locator('#lblDesNumProcesso').inner_text().strip()
        judge = frame.locator('#lblDesJuiz').inner_text().strip()
        if not re.fullmatch(r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}', number) or not judge:
            raise RuntimeError('Número do processo ou magistrado inválido.')
        return frame, number, judge


def run_batch(control, user, password, confirm, progress=None, should_stop=None, sigilo=None, limit=None, on_failure=None):
    """Motor compartilhado entre terminal e interface; Playwright permanece na mesma thread."""
    emit = progress or (lambda event: print(event.get('message', '')) if event.get('message') else None)
    stopped = should_stop or (lambda: False)
    records = [(n, r) for n, r in control.rows() if control.eligible(r)]
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError('O limite deve ser um número inteiro maior que zero.')
        records = records[:limit]
    emit({'event': 'batch', 'total': len(records)})
    if not records:
        return
    with sync_playwright() as pw:
        emit({'event': 'stage', 'stage': 'Abrir navegador EPROC'})
        browser = pw.chromium.launch(headless=False)
        bot = None
        diagnostic_error = None
        try:
            page = browser.new_page()
            page.set_default_timeout(60000)
            bot = Robo(page, sigilo, lambda stage: emit({'event': 'stage', 'stage': stage}))
            bot.login(user, password)
            password = ''
            for n, record in records:
                if stopped():
                    break
                bot.submitted = False; bot.alerts.clear()
                flow_started = False
                emit({'event': 'current', 'row': n, 'id': record['ID_REGISTRO']})
                try:
                    bot.stage = 'Validação do registro'
                    pdf = validate(record, control.path.parent)
                    control.update(n, record, STATUS='Em execução', ETAPA_ERRO='', MENSAGEM_ERRO='')
                    emit({'event': 'row', 'row': n, 'id': record['ID_REGISTRO'], 'status': 'Em execução'})
                    flow_started = True
                    bot.start(); bot.information(record); bot.subjects(record)
                    bot.party(record, 'ATIVA'); bot.party(record, 'PASSIVA'); bot.documents(pdf)
                    button = bot.confirmation()
                    if stopped() or not confirm(record):
                        raise InterruptedError('Ajuizamento não confirmado; lote interrompido antes da confirmação.')
                    control.update(n, record, STATUS='Verificar protocolo', ETAPA_ERRO='Confirmação de ajuizamento')
                    bot.submitted = True
                    button.click()
                    frame, number, judge = bot.result()
                    control.update(n, record, STATUS='Concluído', NUMERO_PROCESSO_GERADO=number,
                                   MAGISTRADO=judge, ETAPA_ERRO='', MENSAGEM_ERRO='')
                    emit({'event': 'row', 'row': n, 'id': record['ID_REGISTRO'], 'status': 'Concluído',
                          'process': number, 'judge': judge})
                    frame.locator('#btnFechar').filter(visible=True).first.click()
                except Exception as error:
                    previous = control.latest.get(record['ID_REGISTRO'], {}).get('STATUS')
                    status = 'Concluído' if previous == 'Concluído' else ('Verificar protocolo' if bot.submitted else 'Erro')
                    message = str(error)[:2000]
                    diagnostic_error = (bot.stage, message)
                    control.update(n, record, STATUS=status, ETAPA_ERRO=bot.stage, MENSAGEM_ERRO=message)
                    emit({'event': 'row', 'row': n, 'id': record['ID_REGISTRO'], 'status': status,
                          'stage': bot.stage, 'error': message})
                    if isinstance(error, InterruptedError):
                        break
                    keep_diagnostic = len(records) == 1 and on_failure and not isinstance(error, SubjectCompetenceError)
                    if status == 'Erro' and flow_started and not keep_diagnostic:
                        try:
                            bot.abort_petition()
                            emit({'event': 'log', 'message': 'Peticionamento com erro cancelado; próximo registro será iniciado em novo fluxo.'})
                        except Exception as recovery_error:
                            detail = (message + '\nFalha ao cancelar o peticionamento: ' + str(recovery_error))[:2000]
                            control.update(n, record, STATUS='Erro', ETAPA_ERRO=diagnostic_error[0], MENSAGEM_ERRO=detail)
                            emit({'event': 'row', 'row': n, 'id': record['ID_REGISTRO'], 'status': 'Erro',
                                  'stage': diagnostic_error[0], 'error': detail})
                            raise RuntimeError('Não foi possível cancelar o rascunho; lote interrompido para evitar reaproveitamento.') from recovery_error
                    if isinstance(error, SubjectCompetenceError):
                        diagnostic_error = None
            if len(records) == 1 and diagnostic_error and on_failure and not page.is_closed():
                on_failure(*diagnostic_error)
        except Exception as error:
            stage = bot.stage if bot is not None else 'Abrir navegador EPROC'
            if on_failure and bot is not None and not page.is_closed():
                on_failure(stage, str(error))
            raise RuntimeError('Falha na etapa ' + stage + ': ' + str(error)) from error
        finally:
            password = ''
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('planilha', type=Path)
    parser.add_argument('--validar', action='store_true', help='Validar entradas sem abrir navegador')
    parser.add_argument('--protocolar', action='store_true', help='Confirmar ajuizamento automaticamente')
    parser.add_argument('--usuario')
    parser.add_argument('--limite', type=int, default=50, help='Máximo de registros por lote (padrão: 50)')
    parser.add_argument('--sigilo-documento', help='Nome exato da opção; omitido mantém valor carregado')
    args = parser.parse_args()
    control = Controle(args.planilha)
    records = [(n, r) for n, r in control.rows() if control.eligible(r)]
    if not records:
        print('Nenhum registro pendente elegível.'); return
    if args.validar:
        failed = 0
        for n, record in records:
            try:
                validate(record, control.path.parent); print(f'Linha {n}: válida')
            except ValueError as error:
                failed += 1; print(f'Linha {n}: {error}')
        raise SystemExit(1 if failed else 0)
    user = args.usuario or input('Usuário EPROC: ')
    password = getpass.getpass('Senha EPROC: ')
    def confirmation(record):
        if args.protocolar:
            return True
        return input(f'Registro {record["ID_REGISTRO"]}: confira o resumo no navegador. Digite CONFIRMAR para ajuizar: ') == 'CONFIRMAR'

    run_batch(control, user, password, confirmation, sigilo=args.sigilo_documento, limit=args.limite)

if __name__ == '__main__':
    main()
