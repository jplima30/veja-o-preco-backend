# 🚀 Manual de Automação e Validadores (Veja o Preço)

Este guia detalha como operar o ecossistema de coleta, triagem e validação do backend.

---

## 🏗️ 1. Ambientes Virtuais (Venvs)

O projeto utiliza dois ambientes distintos para otimizar o uso de recursos:

### A. `venv_triagem` (Processamento Local)
*   **O que contém**: Playwright (Scraper), EasyOCR (Triagem local), Bibliotecas pesadas.
*   **Quando usar**: Para rodar o robô de redes sociais (`cron_playwright.py`) e a triagem automatizada (`triagem_automatizada.py`).
*   **Caminho**: `/Users/jplima/Documents/veja-o-preco-backend/venv_triagem`

### B. `functions/venv` (Integração Cloud)
*   **O que contém**: Firebase Admin, Gemini SDK, Cloud Functions.
*   **Quando usar**: Para testar a visão da IA, validadores de PDF e integração com o banco de dados real.
*   **Caminho**: `/Users/jplima/Documents/veja-o-preco-backend/functions/venv`

---

## ⚡ 2. Comandos de Execução Rápida (Atalhos)

Use estes comandos para rodar os scripts de **qualquer lugar** do terminal, sem precisar ativar o venv manualmente.

### Rodar Robô de Captura (Instagram/Facebook)
```bash
/Users/jplima/Documents/veja-o-preco-backend/venv_triagem/bin/python3 /Users/jplima/Documents/veja-o-preco-backend/scripts/cron_playwright.py
```

### Rodar Apenas Triagem Automatizada (OCR Local nas imagens baixadas)
```bash
/Users/jplima/Documents/veja-o-preco-backend/venv_triagem/bin/python3 /Users/jplima/Documents/veja-o-preco-backend/scripts/triagem_automatizada.py
```

### Rodar Triagem Local (Sem enviar para a nuvem)
```bash
/Users/jplima/Documents/veja-o-preco-backend/venv_triagem/bin/python3 /Users/jplima/Documents/veja-o-preco-backend/scripts/triagem_local.py
```

---

## 🛠️ 3. Detalhamento dos Scripts por Categoria

### 📸 Coleta e Captura
*   `cron_playwright.py`: O "Cérebro". Entra nas redes sociais, tira prints e salva imagens.
*   `captura_visivel.command`: Script utilitário para abrir um terminal macOS e rodar o robô visivelmente.

### 🔍 Triagem e Filtragem (OCR)
*   `triagem_automatizada.py`: O "Filtro". Analisa as imagens baixadas via EasyOCR. Aplica regras rigorosas:
    - **Anti-Data**: Ignora blocos com `/`.
    - **Anti-Ruído**: Descarta blocos com mais letras que números sem `R$`.
    - **Mínimo 2 Dígitos**: Exige `10` ou `R$ 9`.
*   `enviar_triagem.py`: O "Despachante". Acionado automaticamente pela triagem para enviar apenas os frames aprovados para a API do Gemini na nuvem.
*   `triagem_local.py`: Versão de segurança para validar novas regras de OCR sem gastar API ou subir dados.
*   `limpar_bebidas.py`: Script de limpeza pós-extração para remover álcool.

### 📑 Validadores de Encarte (PDF)
*Esses scripts simulam o comportamento do backend para ler PDFs de supermercados.*
*   `validador_mateus.py`: Testa o Mix Mateus.
*   `validador_atacadao.py`: Testa o Atacadão.
*   `validador_economico.py`: Testa o Econômico.

### 🤖 Inteligência Artificial e Nuvem
*   `testar_visao.py`: Envia uma imagem para a API de Visão do Gemini (Multimodal) para extrair JSON de ofertas.
*   `testar_integracao.py`: Valida se o fluxo do robô -> nuvem -> firestore está funcionando.

### 📊 Auditoria e Banco
*   `ver_ofertas_banco.py`: Mostra as últimas ofertas salvas no Firestore.
*   `auditoria_dashboard.py`: Gera um resumo local de como está a saúde dos dados.

---

## ⏰ 4. Automação Agendada (LaunchAgents)

O robô está programado para rodar automaticamente via macOS LaunchAgent:
- **Horários**: 10:00 e 14:00 (Seg-Sáb).
- **Arquivo de Configuração**: `com.vejaopreco.captura.visivel.plist` em `~/Library/LaunchAgents`.

Para verificar se o agendamento está ativo:
```bash
launchctl list | grep vejaopreco
```

---

> [!TIP]
> **Dica de Ouro**: Sempre olhe os logs `cron_playwright.log` se algo parecer não estar coletando. Eles detalham cada clique do robô.
