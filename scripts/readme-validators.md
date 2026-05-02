# 🚀 Manual de Automação e Validadores (Veja o Preço)

Este guia detalha como operar o ecossistema de coleta, triagem e validação do backend.

---

## 🔥 0. Iniciando o Ambiente (Firebase)

Para que os validadores e a IA funcionem localmente, você **deve** iniciar o emulador do Firebase:

```bash
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES && firebase emulators:start
```

---

## 🏗️ 1. Ambientes Virtuais (Venvs)

O projeto utiliza dois ambientes distintos. Ative-os quando quiser rodar comandos simples (ex: `python3 script.py`):

*   **Ambiente Triagem (Playwright/OCR)**:
    ```bash
    source /Users/jplima/Documents/veja-o-preco-backend/venv_triagem/bin/activate
    ```
*   **Ambiente Functions (Firebase/IA)**:
    ```bash
    source /Users/jplima/Documents/veja-o-preco-backend/functions/venv/bin/activate
    ```

---

## ⚡ 2. Comandos para COPIAR E COLAR (Fora do Venv)

Use estes comandos de **qualquer lugar**, sem precisar ativar nada. Eles já chamam o Python correto:

### 📸 Captura e Robô
```bash
/Users/jplima/Documents/veja-o-preco-backend/venv_triagem/bin/python3 /Users/jplima/Documents/veja-o-preco-backend/scripts/cron_playwright.py
```

### 🔍 Triagem Automatizada (OCR Local + Envio Cloud)
```bash
/Users/jplima/Documents/veja-o-preco-backend/venv_triagem/bin/python3 /Users/jplima/Documents/veja-o-preco-backend/scripts/triagem_automatizada.py
```

### 🧪 Testar Visão (IA Gemini)
```bash
/Users/jplima/Documents/veja-o-preco-backend/functions/venv/bin/python3 /Users/jplima/Documents/veja-o-preco-backend/scripts/testar_visao.py
```

### 📊 Ver Ofertas no Banco (Firestore)
```bash
/Users/jplima/Documents/veja-o-preco-backend/functions/venv/bin/python3 /Users/jplima/Documents/veja-o-preco-backend/scripts/ver_ofertas_banco.py
```

---

## 🛠️ 3. Comandos para uso DENTRO do Venv

Se você já deu `source venv_triagem/bin/activate`, use estes comandos curtos:

### No Ambiente `venv_triagem`:
*   **Rodar Robô**: `python3 scripts/cron_playwright.py`
*   **Rodar Triagem**: `python3 scripts/triagem_automatizada.py`
*   **Testar OCR Local**: `python3 scripts/triagem_local.py`
*   **Dashboard de Saúde**: `python3 scripts/auditoria_dashboard.py`

### No Ambiente `functions/venv`:
*   **Iniciar Firebase Emulator**: `export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES && firebase emulators:start`
*   **Testar IA**: `python3 scripts/testar_visao.py` *(Requer Firebase Emulator ligado)*
*   **Validar PDF Atacadão**: `python3 scripts/validador_atacadao.py`
*   **Validar PDF Mateus**: `python3 scripts/validador_mateus.py`
    *   *Comportamento*: Processa **todos** os encartes únicos por padrão.
    *   *Uso Individual*: `python3 scripts/validador_mateus.py [ID]` (ex: `python3 scripts/validador_mateus.py 3`)
    *   *Requisito*: Firebase Emulator ligado.

---

## 🧹 4. Faxina Semanal (Limpeza Automática)

O script `triagem_automatizada.py` realiza uma limpeza automática para economizar espaço em disco.

**Quando ocorre?**
Sábados (após as 12:00h) ou Domingos, na primeira vez que o script for executado.

**O que é apagado?**
1.  `auditoria_visual/YYYY-MM-DD_Dia`: Todas as pastas de fotos brutas (prints originais do robô).
2.  `auditoria_visual/TRIAGEM_AUTOMATIZADA/YYYY-MM-DD_Dia`: Todas as pastas de resultados da triagem local (fotos filtradas).

> [!NOTE]
> A limpeza remove apenas as fotos das pastas datadas da semana atual para manter o disco leve. Os dados extraídos já estarão salvos no Firebase.

---

## ⏰ 5. Agendamento (macOS LaunchAgent)

O robô roda sozinho às **10:00** e **14:00** (Seg-Sáb).
Para verificar o status:
```bash
launchctl list | grep vejaopreco
```

> [!TIP]
> **Dica**: Logs de erro ficam em `scripts/cron_playwright.log`. Se o robô travar, verifique este arquivo primeiro.
