# Robô de peticionamento EPROC TJSP 2º grau

Implementação do fluxo informado para **homologação**, executada no Windows com Python e Playwright. Lê uma linha por ação na aba `Registros`, inclui uma parte ativa e uma passiva, anexa a petição e grava processo e magistrado na mesma linha.

## Conteúdo disponível

- `robo.py`: automação do EPROC com Playwright e Chromium; execução pelo terminal ou pela interface.
- `controle.py`: leitura e validação da planilha, gravação de resultados e recuperação pelo diário `.controle.jsonl`.
- `interface.py` e `web/`: painel local no navegador para selecionar e validar a planilha, acompanhar o lote, confirmar ajuizamentos e interromper a execução.
- `modelo_peticionamento_eproc_2g.xlsx`: planilha modelo com a aba `Registros` vazia e orientações de preenchimento.
- `tests/`: testes automatizados de controle, execução, interface, navegador simulado e empacotamento.
- `instalar.ps1` e `iniciar_interface.bat`: instalação das dependências e inicialização da interface pelo código-fonte.
- `executavel.py`, `gerar_executavel.py`, `gerar_executavel.bat` e `requirements-build.txt`: inicialização e construção do executável Windows com PyInstaller.
- `.github/workflows/tests.yml`: execução dos testes no GitHub Actions, em Windows com Python 3.12.
- `.gitignore` e `.gitattributes`: exclusão de arquivos operacionais e configuração dos finais de linha.
- `CONTRIBUTING.md`: orientações de desenvolvimento.

Planilhas preenchidas, diários, PDFs, referências de telas reais, backups, ambientes Python e executáveis locais ficam fora do repositório. Os testes incluem suas próprias telas simuladas.

O código implementa confirmação manual ou automática, limite padrão de 50 registros e bloqueio de nova tentativa para registros concluídos, em execução ou com protocolo incerto. A existência do código, dos testes e do executável não substitui a validação acompanhada do fluxo real no EPROC de homologação.

## Executável para Windows

O repositório contém os scripts para construir o executável; binários e ZIPs locais não são versionados. Gere o pacote a partir do código que pretende distribuir. A pasta do executável inclui `_internal`, com as dependências e o navegador Chromium.

Para gerar novamente no Windows, com Python instalado, dê dois cliques em **gerar_executavel.bat**. Não é necessário abrir o PowerShell: o arquivo abre sua própria janela, instala as dependências de construção, baixa o Chromium e gera o pacote. Na primeira construção é necessária conexão com a Internet.

Cada construção cria uma pasta de versão exclusiva, preservando as versões anteriores. O resultado será:

- `dist/<versao>/EPROC-Peticionamento/EPROC-Peticionamento.exe`: interface sem janela de terminal.
- `dist/EPROC-Peticionamento-<versao>.zip`: pacote para copiar para outro Windows.
- `abrir_ultima_versao.bat`: lançador gerado para a versão recém-construída; também fica fora do Git.

Encerre a versão anterior antes de abrir a nova. Confira se o ZIP abre e pode ser extraído integralmente antes de distribuí-lo.

Extraia **a pasta inteira**, incluindo `_internal`. Não mova somente o .exe. O computador de uso não precisa de Python, Java ou PowerShell para executar o pacote; o navegador de automação está incluído. A execução ainda exige acesso ao EPROC e aos PDFs locais.

Teste o pacote no Windows: abra o .exe, selecione e valide a planilha, confira o limite de 50, execute um registro acompanhado na homologação e verifique gravação dos resultados. Feche por **Encerrar programa**, disponível somente quando não há lote ativo. Se houver execução, use **Interromper execução** e aguarde o término antes de encerrar. Fechar a aba do navegador sozinho não encerra o programa. Um segundo clique no .exe reabre a interface já ativa.

A construção é específica para Windows; o script não oferece compilação cruzada. Este README não registra uma validação operacional do pacote existente ou do protocolo real. A suíte de testes usa cenários simulados, descritos na seção Testes.

## Instalação no Windows

Instale Python 3.12 ou superior com o launcher `py`. Baixe este projeto, abra o PowerShell na pasta e execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\instalar.ps1
```

O script cria `.venv`, instala as versões de `requirements.txt` e o Chromium do Playwright. As dependências de execução são Playwright 1.58.0 e openpyxl 3.1.5. Não exige certificado digital para o fluxo descrito. O login solicita usuário e senha na interface ou no terminal, conforme o modo de uso; a senha não é gravada no projeto ou na planilha.

## Planilha

Copie `modelo_peticionamento_eproc_2g.xlsx` para um arquivo de trabalho. Preencha a aba `Registros` conforme a aba `Instruções`. Feche o arquivo no Excel antes de executar. Mantenha CPF, CNPJ, código do assunto e número de processo como **texto**, preservando zeros iniciais.

Informe o caminho completo do PDF no Windows, por exemplo:

```text
C:\EPROC2G\peticoes\peticao.pdf
```

Para arquivos do OneDrive, selecione **Sempre manter neste dispositivo**. Caminhos relativos são resolvidos a partir da pasta da planilha. Cada registro precisa de `ID_REGISTRO` único. Os dados de identificação precisam corresponder a partes já cadastradas no EPROC.

Valide as entradas antes de abrir o navegador:

```powershell
.\.venv\Scripts\python.exe robo.py .\trabalho.xlsx --validar
```

## Interface no navegador (recomendada)

Usando o código-fonte, após a instalação, dê dois cliques em **iniciar_interface.bat**. Após construir o executável, use **abrir_ultima_versao.bat** ou abra **EPROC-Peticionamento.exe** na pasta da versão. O programa abre a interface no navegador padrão do Windows. Na execução pelo arquivo `.bat`, mantenha a janela do programa aberta durante o lote.

1. Clique em **Escolher** para selecionar a planilha local. Também é possível informar o caminho no campo. A seleção valida os registros; após uma alteração na planilha, clique em **Validar planilha** novamente.
2. Informe usuário e senha do EPROC. O programa não salva a senha.
3. Defina o **Limite de registros neste lote**, inicialmente 50. O limite inclui tentativas que terminam em erro. Registros já concluídos ou com protocolo incerto são ignorados. Escolha **Confirmar cada registro** ou **Automática para todo o lote** e clique em **Iniciar lote**.
4. Acompanhe a etapa atual, progresso e resultados. O robô abre outra janela de navegador para o EPROC.
5. No modo manual, confira o resumo nessa janela e use **Confirmar ajuizamento** na interface. No modo automático, essa confirmação é enviada para cada registro elegível.
6. **Interromper execução** aguarda o registro atual terminar. Se o robô estiver aguardando sua confirmação, encerra a espera sem ajuizar e registra a interrupção na planilha.

A interface inicia com confirmação automática selecionada. Para uma primeira execução acompanhada, escolha **Confirmar cada registro** e limite 1. A opção **Manter navegador aberto após erro (limite 1)** permite inspecionar uma falha; use Interromper execução para encerrar a inspeção. Erros de competência de assunto seguem o tratamento de cancelamento, sem manter a inspeção aberta.

Os resultados são gravados na planilha original selecionada. A validação na interface é somente leitura. Erros de entrada são apresentados na tabela; durante a execução, o robô registra o erro correspondente e passa ao próximo registro. Uma falha de persistência encerra o lote.

Se o botão de seleção não abrir a janela de arquivos, informe o caminho da planilha manualmente. A seleção usa o suporte a Tkinter incluído na instalação usual do Python para Windows.

A interface escuta apenas no computador local, em `127.0.0.1`, e usa uma chave temporária da sessão para suas ações. Não depende de Java, Node ou serviços externos. Para trocar a porta, execute:

```powershell
.\.venv\Scripts\python.exe interface.py --port 8766
```

Não feche a janela do programa durante um registro em andamento. Para encerrar, solicite a parada na interface, espere o lote terminar e então feche o programa. Interrupções forçadas são tratadas pelas regras de recuperação da planilha e diário.

## Execução pelo terminal

Na primeira execução, use um registro de teste e acompanhe o navegador:

```powershell
.\.venv\Scripts\python.exe robo.py .\trabalho.xlsx
```

O robô preenche o fluxo, anexa e confirma o documento, abre o resumo e aguarda o operador digitar `CONFIRMAR` no terminal antes de confirmar o ajuizamento. Para processar um lote com confirmação automática:

```powershell
.\.venv\Scripts\python.exe robo.py .\trabalho.xlsx --protocolar
```

O endereço está fixado em `https://eproc-2g-sp-hml.tjsp.jus.br/`. Essa opção confirma o ajuizamento de cada registro elegível. O fluxo usa a opção **Finalizar**, sem gerar novas assinaturas digitais. A autenticação com dois fatores, caso exigida, ainda não tem tratamento automático.

## Regras implementadas

- Perfil ADVOGADO; pesquisa Petição Inicial no menu lateral.
- Tribunal de Justiça de São Paulo; área e competência Direito Privado.
- Classe exata da planilha, aguardando a atualização da página.
- Sigilo do processo mantido; valor da causa Não se aplica quando o campo estiver visível; plantão desmarcado.
- Processo originário quando indicado; TJSP - PRIMEIRO GRAU; Juízo carregado automaticamente.
- Assunto por código, com busca pelo nome quando não houver resultado e houver nome informado. A comparação do nome ignora acentos, maiúsculas/minúsculas e espaços repetidos; resultados ambíguos geram erro. A inclusão e a indicação de assunto principal são conferidas antes de avançar.
- Uma parte por polo, ambas principais. CPF para Pessoa Física, CNPJ para Pessoa Jurídica, nome para Entidade.
- Entidades: selecionar a sugestão cadastrada, aceitando CNPJ junto do nome. Quando informado, o CNPJ da planilha ajuda a identificar o cadastro correto; ambiguidades geram erro.
- Em mandado de segurança, conferir e incluir o Ministério Público do Estado de São Paulo já apresentado no polo passivo.
- Justiça Gratuita da parte ativa conforme a planilha; vazio mantém o carregado.
- Tipo do documento PETIÇÃO INICIAL. Sigilo do documento mantém o carregado por padrão. É possível definir a opção exata com `--sigilo-documento "Sem Sigilo (Nível 0)"`.
- Informações adicionais não são preenchidas neste projeto. **Em projetos futuros, revisar liminar, prioridades, intervenção do Ministério Público e as demais opções.**
- Documento conferido na tabela pelo nome, tamanho positivo e tipo INIC antes de Finalizar.
- Upload: aguardar a confirmação do servidor e fechar o aviso conhecido de PDF pesquisável. Ao encontrar uma petição já anexada, prosseguir somente se houver um único documento com nome, tamanho, tipo e eventual sigilo esperados. Nome e tamanho não comprovam igualdade do conteúdo do PDF.
- Processo e texto completo do magistrado gravados após a mensagem Processo distribuído; depois, Fechar.

Ao terminar um lote limitado, inicie novamente com a mesma planilha para processar os próximos registros elegíveis. Registros com status Erro permanecem elegíveis e serão tentados novamente na ordem da planilha; corrija as falhas antes do próximo lote. Concluído e Verificar protocolo não são repetidos.

No terminal, o limite padrão também é 50. Para alterá-lo, use `--limite 100`.

## Erros e recuperação

Uma falha antes do ajuizamento registra `Erro`, etapa e mensagem. Se o fluxo já iniciou, o robô cancela o rascunho antes de abrir uma nova Petição Inicial para a próxima linha; se o cancelamento não for confirmado, interrompe o lote. O modo de diagnóstico com limite 1 pode manter a tela aberta para inspeção. A sessão autenticada é reutilizada entre registros. Se a sessão expirar, execute novamente para autenticar.

Não há tratamento específico de repetição ou espera para respostas HTTP 429 nesta versão.

Antes de clicar Confirmar ajuizamento, o robô persiste `Verificar protocolo`. Uma falha ou interrupção depois disso **não provoca nova tentativa automática**. Confira o processo no EPROC antes de tomar qualquer decisão de reprocessamento.

Registros `Concluído`, `Verificar protocolo` ou `Em execução` são ignorados nas novas execuções. Um registro `Em execução` após interrupção precisa ser investigado; não altere o ID para forçar uma tentativa. Registros `Erro` podem ser tentados novamente após corrigir a causa.

O arquivo `trabalho.controle.jsonl`, ao lado da planilha, registra os resultados antes da gravação do Excel. Não o apague: ele evita duplicidade quando uma gravação falha. Na execução seguinte, resultados desse diário são reaplicados à planilha. Se não for possível salvar o Excel ou o diário durante a execução, o lote para: não é seguro continuar sem registrar o controle.

O código não persiste as credenciais de login. Planilhas preenchidas, diários e referências de telas podem conter dados do processo e ficam fora do Git. Mantenha novos arquivos de trabalho em pasta separada do código-fonte. A planilha modelo versionada contém somente cabeçalhos e instruções, sem registros de peticionamento.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes verificam gravação e recuperação do controle, preservação de zeros, bloqueio de duplicidade, continuidade após erros, parada do lote e um fluxo funcional no navegador com páginas simuladas, incluindo upload e confirmação em iframe. Também exercitam a interface HTTP e seu uso no navegador: validação, início, confirmação manual, lote automático, resultados e parada, sem expor credenciais no estado da interface. Nenhuma chamada ao TJSP é feita nos testes.

Na preparação para compartilhamento em 08/10/2026, os 60 testes passaram localmente com o Chromium incluído no projeto. Se o navegador estiver fora do caminho padrão do Playwright, informe seu executável na variável `EPROC_TEST_CHROMIUM` antes de executar os testes. No GitHub Actions, o navegador é instalado pelo workflow; a execução remota só será comprovada após seu primeiro resultado.

O fluxo real foi mapeado a partir de referências de telas e HTML. **A validação do executável e do protocolo real deve ser feita em um teste acompanhado no Windows e no EPROC de homologação**, especialmente senha mascarada, autocompletar de entidades, validação de processo originário e confirmação de ajuizamento. As telas simuladas não comprovam que o protocolo real funciona.

## Compartilhar no GitHub

O código, a interface, os testes, os scripts e a planilha modelo vazia são os arquivos destinados ao repositório. Antes de enviar, confira `git status` e `git diff --cached --stat`. Não force a inclusão de arquivos ignorados.

Após criar ou escolher um repositório vazio no GitHub, substitua a URL abaixo pelo endereço do seu repositório:

```powershell
git commit -m "Preparar projeto EPROC 2G para compartilhamento"
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

Os comandos acima pressupõem que o Git já foi inicializado e os arquivos revisados foram adicionados ao índice. Em uma cópia extraída do ZIP de compartilhamento, execute primeiro `git init -b main` e `git add .`. Se o repositório remoto já tiver arquivos ou histórico, integre esta versão em um clone dele antes de enviar.

Cada tarefa de desenvolvimento já usa ambiente isolado: utilize o checkout existente, sem criar worktrees, salvo pedido explícito.
