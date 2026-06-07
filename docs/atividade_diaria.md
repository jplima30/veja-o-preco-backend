# Diário de Atividade de Triagem - App Veja o Preço

Registro das execuções do motor de triagem automatizada e manual.

---

## [2026-06-07] - Domingo
- **Status:** Concluído.
- **Atividade:** Manutenção de emergência — Faturamento, Migração de Modelo e Deploy.
- **Infraestrutura:**
  - Diagnosticada suspensão do faturamento Firebase (débito R$13,57 — API Gemini de Abril e Maio).
  - Faturamento reestabelecido pelo usuário via pagamento do débito.
  - Firebase CLI atualizado: `15.17.0` → `15.19.1`.
- **Desenvolvimento:**
  - Migração do modelo `gemini-3.1-flash-image-preview` (depreciação: 25/06/2026) para `gemini-3.1-flash-image` (GA) nas funções `buscar_encarte_assai` e `extrair_dados_imagem`.
  - Deploy completo das 11 Cloud Functions após reativação do faturamento.
- **Resultado:** Sistema 100% operacional. Sem erros 503/403.

## [2026-05-14] - Quinta-feira
- **Status:** Concluído.
- **Atividade:** Resolução de instabilidades no login do Playwright (Erro ERR_TOO_MANY_REDIRECTS).
- **Desenvolvimento:** Remoção da biblioteca stealth devido à detecção ativa pelo Instagram, adoção de perfil persistente "natural" com User-Agent atualizado e fallback para bloqueios de conta (`logar_instagram.py`).

## [2026-05-08] - Sexta-feira
- **Status:** Concluído.
- **Atividade:** Resolução de instabilidades no login do Playwright.
- **Desenvolvimento:** Criação do script dedicado `logar_instagram.py` com blindagem Stealth, e mapeamento do mecanismo de fallback de sessão no Chromium.

## [2026-05-03] - Domingo
- **Status:** Em andamento (Triagem das 14h concluída).
- **Atividade:** Processamento de encartes e validação de ofertas.
- **Destaque:** Implementação de travas de segurança na faxina semanal e início da sincronia de histórico de commits retroativos.

## [2026-05-02] - Sábado
- **Status:** Concluído.
- **Janelas:** 10h, 14h e Manual.
- **Atividade:** Grande volume de extração de Reels (Assai, Líder, Formosa).
- **Nota:** Executada faxina semanal de disco.

## [2026-05-01] - Sexta-feira
- **Status:** Concluído (Retroativo).
- **Janelas:** 10h, 14h e Manual.
- **Atividade:** Manutenção de backend e ajuste na lógica de ofertas.
- **Desenvolvimento:** Refatoração de scripts de extração e correção de bugs no fluxo de persistência local.
- **Infraestrutura:** Validação de regras de segurança e emulação do Firebase para testes de integração de ofertas.
- **Triagem:** Processamento de encartes sazonais (Mês das Mães) no Mateus Site e atualização de preços MM Guerreirão com registro no Firestore.
