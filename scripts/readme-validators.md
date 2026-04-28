# Guia de Validadores e Testes

Este diretório contém scripts Python para validar os robôs de extração sem precisar do App iOS.

## 1. Validador do Mix Mateus
Testa a descoberta de encartes e a leitura de PDFs.
```bash
python3 scripts/validador_mateus.py
```

## 2. Testador de Visão Computacional (Líder / Formosa / Guerreirão)
Testa a extração de dados a partir de fotos de redes sociais no emulador local.
```bash
python3 scripts/testar_visao.py 'URL_DA_IMAGEM_AQUI'
```

### Requisitos para o Testador de Visão:
- O emulador do Firebase deve estar rodando (`npx firebase-tools emulators:start --only functions`).
- O ambiente virtual deve estar ativo (`source functions/venv/bin/activate`).

## 3. Motor de Automação de Redes Sociais
O script principal que coordena a busca no Instagram e Facebook (Líder, Formosa, Guerreirão BR, Assaí).
```bash
python3 scripts/cron_playwright.py
```
*Atenção: Este script necessita do Playwright instalado (`pip install playwright` e `playwright install chromium`) e enviará os dados diretamente para a nuvem (produção).*
