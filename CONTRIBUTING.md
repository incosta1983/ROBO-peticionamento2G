# Desenvolvimento

Use Python 3.12 ou superior. No Windows, execute `instalar.ps1` conforme o README.

Antes de propor mudanças, execute:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes usam páginas simuladas e não acessam o TJSP. Para testar o fluxo real, use o ambiente de homologação, um registro e confirmação manual; confira o resultado no EPROC e na planilha.

Inclua na descrição da alteração o comportamento modificado e a validação realizada. Testes que dependem de novas telas devem usar fixtures sintéticas.

Não inclua credenciais, cookies, sessões, dados pessoais, planilhas preenchidas, diários de execução, PDFs ou capturas de processos. As referências locais em `txt/` ficam fora do repositório; as telas necessárias aos testes estão em `tests/`.

Executáveis e arquivos gerados não fazem parte do código-fonte. Gere um novo pacote no Windows a partir da versão que deseja distribuir e confira sua integridade antes de compartilhá-lo.
