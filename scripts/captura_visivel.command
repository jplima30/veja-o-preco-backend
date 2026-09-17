#!/bin/bash
# Arquivo gerado para rodar a captura do Veja o Preço de forma visível
cd /Users/jplima/Documents/veja-o-preco-backend/scripts
DATA=$(date +%Y-%m-%d)
HORA=$(date +%H)
if [ "$HORA" -lt 13 ]; then JANELA="10h"; else JANELA="14h"; fi
LOG_FILE="/Users/jplima/Documents/veja-o-preco-backend/scripts/cron_${DATA}_${JANELA}.log"
/Users/jplima/Documents/veja-o-preco-backend/venv_triagem/bin/python3 cron_playwright.py 2>&1 | tee "$LOG_FILE"
/Users/jplima/Documents/veja-o-preco-backend/functions/venv/bin/python3 resumo_hoje.py 2>&1 | tee -a "$LOG_FILE"
# Mantém cron_hoje.log como cópia da última janela (compatibilidade com gerenciador)
cp "$LOG_FILE" "/Users/jplima/Documents/veja-o-preco-backend/scripts/cron_hoje.log"
