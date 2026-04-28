# Explicação Técnica: Como o Backend Funciona

O backend do "Veja o Preço" é um sistema híbrido que utiliza três níveis de inteligência para capturar ofertas:

## 1. Níveis de Extração
- **API Direta**: Consumo direto de endpoints JSON/GraphQL (Atacadão, Seja Econômico). É a forma mais rápida e barata.
- **Extração via I.A. (PDF)**: Para o Mix Mateus, processamos tabloides digitais usando o Gemini 3.1 Flash Lite (Foco em custo/volume).
- **Híbrido (I.A. Vision + Triagem Local)**: Para o Assaí e redes sociais (Líder, Formosa, Guerreirão BR), usamos um robô local (`cron_playwright.py`). Ele captura imagens/vídeos e utiliza o **EasyOCR** localmente (`triagem_ofertas.py`) para filtrar o que não tem preço. O que for aprovado é enviado para o Gemini 3.1 Flash Image (Elite Vision) na nuvem para extração final.

## 2. Padronização (O Contrato)
Independente de onde venha o dado, o sistema sempre entrega o mesmo formato JSON para o App iOS, garantindo que o frontend nunca quebre.

## 3. Segurança e Performance
- **Headers de Navegador**: O robô `cron_playwright` simula comportamento humano para evitar bloqueios das redes sociais (Error 403).
- **Consumo Consciente**: Todas as chamadas de I.A. monitoram o uso de tokens para controle de custos, e usamos um histórico local (`historico_posts.json`) para nunca processar o mesmo post duas vezes.

---
## 4. Estrutura de Pastas e o que Sobe para a Nuvem

```
veja-o-preco-backend/
│
├── functions/
│   ├── main.py              ← 🔥 OS SCRAPERS REAIS (Cloud Functions)
│   └── ...
│
├── auditoria_visual/            ← 📸 Provas Visuais (Scraping local do Playwright)
│   └── 2026-04-26_Domingo/      ← 🗂️ Pastas separadas automaticamente por dia
│       ├── 10h/                 ← 🕙 Capturas da manhã
│       └── 14h/                 ← 🕑 Capturas da tarde
│
├── scripts/
│   ├── cron_playwright.py       ← 🤖 Robô fantasma (Instagram e Site Assaí)
│   ├── captura_visivel.command  ← 🖥️ Atalho para abrir o robô no Terminal (Mac)
│   ├── triagem_ofertas.py       ← 🧠 Filtro de I.A. Local (OCR)
│   └── ...
```

### O que sobe para o servidor (firebase deploy):
- `functions/main.py` → O código de todos os scrapers e I.A.
- `functions/requirements.txt` → As dependências do projeto.
- `functions/venv/` → **NÃO sobe** (ignorado pelo firebase.json).

### O que fica apenas local (nunca sobe):
- `scripts/` → Utilitários de manutenção e robôs locais.
- `docs/` → Documentação do projeto.
- `auditoria_visual/` → Armazenamento local de imagens.

### Ciclo completo de desenvolvimento:
```
1. Desenvolver localmente no main.py
2. Testar no emulador (grátis e seguro)
3. firebase deploy --only functions
4. Google hospeda o main.py na nuvem 24/7
5. App iOS chama as funções via URL pública
```

---
## 5. Ambientes Virtuais (Python)

O projeto utiliza dois ambientes separados para evitar conflitos:

1. **Ambiente Local de Triagem (`venv_triagem`)**:
   - **Python 3.12**
   - Foco: `easyocr`, `playwright`, `numpy 1.26.4`.
   - Uso: O robô local roda automaticamente dentro deste ambiente para garantir que a I.A. de OCR funcione.

2. **Ambiente da Nuvem (`functions/venv`)**:
   - **Python 3.13**
   - Foco: `firebase-functions`, `google-genai`.
   - Uso: Testes locais das Cloud Functions e deploy.

---
**Comandos e Automação**
- **Agendamento Visível**: No Mac, o robô está agendado via `LaunchAgent` para rodar às **10h e 14h**. Ele abre automaticamente uma janela do **Terminal** para que você acompanhe o status em tempo real.
- **Divisão por Horário**: As capturas são salvas em subpastas (`10h/` ou `14h/`) para evitar confusão entre as ofertas da manhã e da tarde.
- **Limpeza Automática**: O sistema limpa as fotos brutas da semana todo Sábado após as 12h, mantendo apenas o que foi aprovado na triagem.
