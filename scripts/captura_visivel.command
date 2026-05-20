#!/bin/bash
# Arquivo gerado para rodar a captura do Veja o Preço de forma visível
cd /Users/jplima/Documents/veja-o-preco-backend/scripts
LOG_FILE="/Users/jplima/Documents/veja-o-preco-backend/scripts/cron_hoje.log"
/Users/jplima/Documents/veja-o-preco-backend/venv_triagem/bin/python3 cron_playwright.py 2>&1 | tee "$LOG_FILE"
