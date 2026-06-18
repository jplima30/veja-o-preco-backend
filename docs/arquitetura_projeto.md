# Arquitetura do Projeto — Veja o Preço (Backend)

Este documento descreve a evolução da arquitetura, decisões técnicas e o estado atual do sistema de monitoramento de preços.

---

**Sessão 1 a 3 (Base e Scrapers Iniciais)**
(Conteúdo anterior omitido para brevidade, mas preservado no histórico)

---

**Sessão 4 (Mapeamento de Seletores e Quick Wins)**

**Data:** 20 de Abril de 2026
**Objetivo:** Consolidar os seletores CSS/Xpath para os supermercados que possuem site e definir a estratégia de extração.

**Descobertas:**
1. **Econômico e Atacadão:** Utilizam estruturas similares baseadas em cards de produtos, facilitando a extração via `requests` + `BeautifulSoup`.
2. **Guerreirão AM:** Possui um site com carregamento dinâmico limitado, mas os dados de oferta estão expostos no HTML inicial.

**Status Atual:** Mapeamento concluído. Iniciando a implementação das funções de extração de "Quick Wins" (Guerreirão AM, Econômico e Atacadão).

---

**Sessão 5 (A Era da Visão e Gemini 3.1)**

**Data:** 21-22 de Abril de 2026
**Objetivo:** Finalizar Mix Mateus (PDF) e inaugurar a Visão Computacional para o Guerreirãon BR.

**Descobertas e Decisões:**
1. **Migração para Gemini 3.1 Flash Lite:** Adotamos o modelo mais recente (`gemini-3.1-flash-lite`) por ser otimizado para extrações rápidas e de baixo custo, mantendo alta precisão.
2. **Telemetria de Tokens:** Implementamos um sistema de monitoramento de custos que injeta o uso de `prompt` e `resposta` em cada JSON, permitindo controle total do ROI.
3. **Padrão Vision AI:** Criamos a função `extrair_dados_imagem` como solução universal para mercados sem site (Líder, Formosa, Guerreirão BR).
4. **Solução 403 e Truncamento de URL:** Identificamos que links de redes sociais devem ser enviados via **POST** para evitar truncamento de caracteres especiais e exigem headers de navegador real para evitar o bloqueio 403 do Meta.

**Status Atual:** 5 mercados concluídos (Seja Econômico, Atacadão, Guerreirão AM, Mix Mateus e Guerreirão BR). O backend agora possui "olhos" e está pronto para o Assaí e para as redes locais (Líder/Formosa).

---

**Sessão 6 (Dominando as Redes Locais)**

**Data:** 23 de Abril de 2026
**Objetivo:** Validar Vision AI no Líder e Formosa, e implementar filtros de categoria.

**Descobertas e Decisões:**
1. **Regra Food Only:** Implementamos um filtro rigoroso no prompt do Gemini para ignorar Bazar, Bebidas Alcoólicas e Eletrônicos, garantindo um banco de dados de alimentos limpo.
2. **Validação Líder:** Teste bem-sucedido com ofertas do Instagram (Pizza Semipronta). I.A. demonstrou alta precisão em categorias de padaria.
3. **Validação Formosa:** Teste bem-sucedido com ofertas do Facebook (Banana Prata). A I.A. extraiu corretamente até a data de validade da oferta ("22/04 a 23/04").
4. **Anti-Hallucination:** Refinamos o prompt para impedir que a I.A. invente URLs de imagens (ex: links do Unsplash), forçando o campo a retornar vazio quando o dado não existe.

**Status Atual:** 7 unidades/redes mapeadas e validadas (Seja Econômico, Atacadão, Guerreirão AM, Guerreirão BR, Mix Mateus, Líder e Formosa). Arco de supermercados principais concluído. Assaí em monitoramento.

---

**Sessão 7 (O Banco de Dados Vivo — Firestore)**

**Data:** 24-25 de Abril de 2026
**Objetivo:** Integrar persistência no Firestore e validar o fluxo completo API → Parse → Banco de Dados.

**Resultados:**
1. **Arquitetura Firestore:** Definidas 3 coleções (`/produtos`, `/ofertas`, `/supermercados`) com modelagem produto-oferta separada para suportar histórico de preços.
2. **Módulo de Persistência:** Implementadas funções `normalizar_nome()`, `buscar_imagem()` (3 camadas de fallback) e `salvar_produto_e_oferta()` (upsert inteligente com TTL de 7 dias).
3. **Seed Inicial:** 8 supermercados cadastrados via `seed_firestore.py` (Econômico, Atacadão, Guerreirão AM/BR, Mix Mateus, Assaí, Líder, Formosa).
4. **Integração nos 3 Scrapers:** Upsert Firestore integrado em `buscar_encarte_economico`, `buscar_encarte_guerreirao` e `buscar_encarte_atacadao`.
5. **Validação de Ouro:** Teste ponta-a-ponta confirmado com 3 produtos reais salvos no Firestore (Coca Cola R$4.32, Piraquê R$4.77, Vitarella R$5.94).
6. **Documentação:** Checklist unificado (`CHECKLIST_FASES.md`) substituiu o antigo `CHECKLIST_FASE_2.md`. Todos os docs em `/docs` auditados e sincronizados.

**Status Atual:** Backend com persistência funcional. Próxima etapa: endpoint `get_ofertas_do_dia` para o App iOS e automação CRON.

---

**Sessão 8 (Estabilização do Motor de Redes Sociais e Auditoria)**

**Data:** 25-26 de Abril de 2026
**Objetivo:** Finalizar extração em redes sociais, estabilizar IDE e integrar infraestrutura de auditoria.

**Resultados:**
1. **Endpoint Público:** Deploy do `get_ofertas_do_dia` testado e validado via URL pública (consumindo dados reais do Firestore).
2. **Motor Playwright (`cron_playwright.py`):** Sistema reescrito para navegação local em redes sociais. Utiliza um perfil persistente natural (sem bibliotecas de stealth ativas, para evitar loops de bloqueio de conta) e é capaz de "roubar" URLs da aba de network (sniffer) e fatiar vídeos do Reels em frames (imagens múltiplas) baseados no tamanho do vídeo.
3. **Múltiplos Alvos Instagram/Facebook:** Líder, Formosa, Guerreirão BR e Assaí Atacadista integrados com sucesso no Playwright.
4. **Resolução de Conflitos Multimodal:** Aprimoramento da API Gemini Flash 2.5/3.1 para aceitar fluxos mistos (imagens estáticas vs frames de vídeo) em Base64 ou URL direta sem estourar limites.
5. **Auditoria Visual:** Criação de estrutura rotativa automática de pastas (`auditoria_visual/YYYY-MM-DD_Dia`) para salvar os frames do Playwright antes de enviar à nuvem.
6. **IDE Tuning:** Travamento forçado das rotas do Python no `.vscode/settings.json` e `pyrightconfig.json` para matar os erros fantasmas do Pyright/Pylance (garantindo que o IDE enxergue o `venv` da pasta `functions`).

**Status Atual:** Fase 5 concluída. O backend está sólido, com cronJobs integrados e scrapers robustos.

---

**Sessão 9 (O Nascimento do App — SwiftUI)**

**Data:** 27 de Abril de 2026
**Objetivo:** Iniciar a construção da interface do usuário (UI) e conectar o App ao backend Firebase.

**Planejamento:**
1. **Setup**: Criação do projeto `VejaOPreco` no Xcode usando SwiftUI.
2. **Metodologia**: Abordagem didática "do zero", explicando os fundamentos de Views, Models e Networking.
3. **Design**: Implementação de uma interface premium, focada em visualização de ofertas e preços.

---

**Sessão 10 (Estabilização Final e Triagem Local)**

**Data:** 27-28 de Abril de 2026
**Objetivo:** Resolver conflitos de dependências (Numpy), bugs de runtime na nuvem e consolidar o pipeline de triagem local.

**Resultados:**
1. **Pipeline de Triagem Automatizada:** Implementado o script `triagem_automatizada.py` que utiliza **EasyOCR** localmente para filtrar imagens irrelevantes (posts sem preços) antes do upload. Isso reduz custos de API e evita poluição no banco.
2. **Resolução Numpy/OCR:** Resolvido o conflito de versões entre `EasyOCR` e `Numpy 2.0`. Realizamos o downgrade para `Numpy 1.26.4` e alinhamos `opencv-python-headless` e `tifffile`, garantindo estabilidade no ambiente local.
3. **Gerenciamento de Ambientes:** Isolamos o ambiente de triagem (`venv_triagem`) no Python 3.12, mantendo a compatibilidade com bibliotecas de visão computacional legadas.
4. **Correção de Runtime (Cloud Functions):** Corrigido o bug `eh_video is not defined` no backend, garantindo que o processamento de imagens e frames de vídeo via Gemini funcione sem erros 500.
5. **Faxina Automática:** Adicionada lógica de limpeza semanal de imagens brutas (Sábados/Domingos) para otimizar o espaço em disco do servidor local.

**Status Atual:** Backend 100% estável e automatizado. Fase 5 concluída com sucesso. Próximo passo: Iniciar o desenvolvimento do Aplicativo iOS (SwiftUI).

---

**Sessão 11 (Auto-Organização e Hierarquia Temporal)**

**Data:** 28 de Abril de 2026
**Objetivo:** Organizar as capturas diárias em janelas de tempo (`10h`, `14h`) e lidar com pastas órfãs.

**Resultados:**
1. **Nova Estrutura de Pastas:** As capturas agora são salvas em subpastas temporais dentro do dia (ex: `2026-04-28_Terca/10h/`).
2. **Organizador de Órfãos:** Implementada função `limpar_pastas_orfas` que move automaticamente qualquer pasta de loja solta na raiz do dia para a subpasta `manual`.
3. **Acionamento Automático:** O `cron_playwright.py` agora dispara a triagem automaticamente ao finalizar, passando o contexto da janela atual.

---

**Sessão 12 (Resiliência Assaí e Faxina Inteligente)**

**Data:** 28 de Abril de 2026
**Objetivo:** Refinar o tratamento de erros do Assaí e validar a lógica de limpeza semanal com a nova estrutura.

**Resultados:**
1. **Resiliência Assaí:** Ajustado o log para "Nenhum encarte encontrado" em casos de transição de ofertas no site oficial, evitando disparos falsos de erro.
2. **Validação da Faxina:** Confirmado que a lógica de limpeza semanal (`realizar_faxina_semanal`) abrange as novas subpastas (`10h`, `14h`, `manual`), pois atua na raiz da pasta datada.
3. **Estabilização do Pipeline:** Backend operando em fluxo contínuo: Captura -> Organização -> Triagem OCR -> Upload Nuvem -> Registro de Histórico.

---

**Sessão 13 (Diagnóstico e Consolidação da Estrutura)**

**Data:** 28 de Abril de 2026 (Final da Noite)
**Objetivo:** Implementar modo de teste e validar a organização de pastas órfãs para garantir a estabilidade do fluxo de triagem.

**Resultados:**
1. **Modo de Diagnóstico:** O script `triagem_automatizada.py` agora suporta o comando `test <caminho>`, permitindo validar a organização de pastas sem depender do relógio do sistema ou disparos de cron.
2. **Organização de Órfãos:** Validada a movimentação automática de pastas de lojas para a subpasta `manual` quando capturadas fora das janelas padrão (`10h`/`14h`).
3. **Robustez da Triagem:** A lógica de triagem foi atualizada para processar recursivamente todas as subpastas da janela selecionada, garantindo que nenhum item seja ignorado.

---

**Sessão 16 (Blindagem de Categorias e Modelos Gemini 3.1)**

**Data:** 30 de Abril de 2026
**Objetivo:** Implementar camadas de segurança para garantir que apenas itens de supermercado entrem no banco de dados.

**Resultados:**
1. **Modelos de Elite (Gemini 3.1):** Consolidamos o uso do `gemini-3.1-flash-image-preview` para visão (fotos/vídeos) e `gemini-3.1-flash-lite` para textos (PDFs), garantindo o melhor equilíbrio entre inteligência visual e custo.
2. **Whitelist de Categorias:** O sistema agora opera sob um regime de "Whitelist" (Alimentação, Higiene e Limpeza). Qualquer item fora desses eixos é descartado.
3. **Filtro de Categoria em Código:** Adicionamos uma trava de segurança no `functions/main.py` que lê a categoria retornada pela IA. Se for "Bazar", "Eletrônicos" ou "Bebidas Alcoólicas", o registro é abortado antes de chegar ao Firestore.
4. **Manual de Automação 2.0:** O `readme-validators.md` foi reescrito para separar comandos "Dentro vs Fora do Venv", facilitando o uso rápido via terminal.

**Status Atual:** Sistema protegido contra poluição de dados (pneus, TVs, etc.) e documentação operacional simplificada.

---

**Sessão 17 (Unificação Mateus e Padronização Browser)**

**Data:** 01 de Maio de 2026
**Objetivo:** Unificar o scraper do Mateus no fluxo `cron_playwright.py` e consolidar a arquitetura baseada em nuvem.

**Resultados:**
1. **Unificação Mateus (Site)**: O Mateus deixou de ser um script isolado e foi integrado ao `cron_playwright.py`. Agora ele usa navegação Playwright para capturar o link direto do PDF.
2. **Modelo Gemini 3.1 Confirmado**: Reafirmamos o uso dos modelos `gemini-3.1-flash-image-preview` e `gemini-3.1-flash-lite` como os motores oficiais de extração na nuvem.
3. **Fluxo de Dados PDF**: O link do PDF capturado pelo Mateus é enviado diretamente para o `ENDPOINT_PDF`. O Gemini 3.1 Flash Image processa o documento na nuvem, eliminando a necessidade de conversão local.
4. **Resiliência de Interface**: Adicionada lógica de interação para modais (Escape) e botões de seleção de loja no site do Mateus para evitar quebras em mudanças de layout.

---

**Sessão 18 (Blindagem de Dados e Otimização Firestore)**

**Data:** 02 de Maio de 2026
**Objetivo:** Implementar travas de categoria, batching no Firestore e limpeza automática de duplicatas.

**Resultados:**
1. **Batch Firestore (x500)**: Implementamos o uso de `WriteBatch` para realizar até 500 escritas de uma só vez. Isso reduz drasticamente o tempo de processamento e o consumo de recursos na nuvem.
2. **Proteção Contra Lixo (Whitelist)**: Adicionada uma camada de validação em código (`functions/main.py`) que descarta itens de categorias proibidas (Sandálias, Eletrônicos, Bazar) antes mesmo de tentarem entrar no banco de dados.
3. **Economia de IA (Histórico Local)**: O arquivo `historico_posts.json` agora é o guardião local. Ele impede que o mesmo post do Instagram seja enviado para análise de IA mais de uma vez por dia, gerando economia real de créditos.
4. **Resiliência de OCR**: Melhoria na triagem local para ignorar ruídos visuais de lojas de departamento que possam "vazar" nos perfis oficiais dos supermercados.

**Status Atual:** Sistema blindado contra poluição, otimizado para custo zero e com deploy de produção 100% atualizado. Próxima etapa: Desenvolvimento da UI Premium em SwiftUI.

---

**Sessão 19 (Agendamento Nativo MacOS e Logs)**

**Data:** 20 de Maio de 2026
**Objetivo:** Clarificar o mecanismo de agendamento automático no MacOS e implementar um sistema de logs visível e persistente.

**Resultados:**
1. **LaunchAgent vs CRON**: Mapeado que a automação não roda via `cron` tradicional, mas sim através do `launchd` do MacOS (`com.vejaopreco.captura.visivel.plist`). Isso permite abrir ativamente o Terminal para rodar os scripts, garantindo que variáveis de ambiente como `$PATH` e bibliotecas compiladas do Homebrew carreguem corretamente.
2. **Log em Tempo Real (`tee`)**: Atualizado o `captura_visivel.command` para que a saída do robô continue visível no pop-up do Terminal, mas seja paralelamente salva no arquivo `cron_hoje.log`. Isso abandona a geração antiga (e estática) do `cron_playwright.log` e permite debugar possíveis falhas nas janelas das 10h e 14h.
3. **Fuga da Descontinuação (Legacy Sunset)**: Identificamos que o endpoint `buscar_encarte_assai` ainda utilizava o `gemini-1.5-flash` (marcado para sunset pelo Google). Atualizamos o motor para o `gemini-3.1-flash-image-preview`, que é a ferramenta multimodal com a melhor relação de custo-benefício, garantindo a sobrevida da função e evitando quedas do serviço.

---

*Última atualização: 18/06/2026 — Sessão 21: Resiliência em Captura de Reels.*

---

**Sessão 20 (Migração de Modelos e Resolução de Faturamento)**

**Data:** 07 de Junho de 2026
**Objetivo:** Resolver interrupção do serviço por faturamento Firebase suspenso, migrar modelo Gemini depreciado e atualizar Firebase CLI.

**Contexto:**
O sistema estava retornando erros `503` nas Cloud Functions e `403 Forbidden` no Secret Manager. A causa raiz foi identificada como a suspensão do faturamento Firebase por débito em aberto de **R$13,57** (custos de API Gemini de Abril e Maio de 2026).

**Resultados:**
1. **Diagnóstico de Custo Confirmado:** 100% dos custos são da API Gemini (extração visual). Cloud Functions = R$0 (coberto pelo free tier do Google). Custo médio: ~R$6,78/mês para o volume atual de encartes.
2. **Migração de Modelo (Urgente):** O modelo `gemini-3.1-flash-image-preview` tinha data de descontinuação em **25/06/2026**. Migramos proativamente para `gemini-3.1-flash-image` (GA) nos dois pontos de uso:
   - `buscar_encarte_assai` (linha ~671 do `main.py`)
   - `extrair_dados_imagem` (linha ~1273 do `main.py`)
   - `gemini-3.1-flash-lite` mantido sem alterações (estável até 05/2027)
3. **Resolução do Faturamento:** Pagamento do débito reestabelecido. Deploy concluído com todas as **11 funções** reamplantadas com sucesso.
4. **Firebase CLI Atualizado:** Versão `15.17.0` → `15.19.1`.

**Modelos Gemini em uso após a sessão:**

| Função | Modelo | Status |
|--------|--------|--------|
| `buscar_encarte_assai` | `gemini-3.1-flash-image` | ✅ GA (estável) |
| `extrair_dados_imagem` | `gemini-3.1-flash-image` | ✅ GA (estável) |
| `extrair_dados_encarte` | `gemini-3.1-flash-lite` | ✅ Estável até 05/2027 |

---

**Sessão 21 (Resiliência em Captura de Reels do Instagram)**

**Data:** 18 de Junho de 2026
**Objetivo:** Corrigir o erro `Page.screenshot: Timeout 30000ms exceeded` que impedia a captura de frames de vídeos (Reels) do Instagram.

**Diagnóstico:**
O CRON da manhã (janela 10h) falhou em **9 Reels** — 6 do Líder (`@supermercadoslider`) e 3 do Assaí (`@assaiatacadistaoficial`). A causa raiz era tripla:
1. O Instagram inicia Reels pausados no modal — o código nunca chamava `video.play()`.
2. O `try/except` envolvia o loop inteiro — um frame com erro abortava todos os outros.
3. Não havia fallback — se os frames falhassem, o post era completamente ignorado.

**Resultados:**
1. **Reprodução Forçada:** O robô agora executa `video.muted = true; video.play()` e aguarda `readyState >= 2` (HAVE_CURRENT_DATA) antes de iniciar a captura.
2. **Resiliência por Frame:** Cada frame é capturado em seu próprio bloco `try/except` com timeout reduzido de **30s → 8s**. Um contador de falhas consecutivas aborta após 3 erros seguidos para não travar o CRON.
3. **Fallback Poster/Thumbnail:** Se nenhum frame for capturado, o sistema extrai o atributo `poster` do elemento `<video>` (thumbnail de alta resolução que o Instagram sempre fornece) e o usa como imagem estática.
4. **Validação Manual:** Teste com `--force` confirmou que os 9 Reels que falhavam de manhã agora são capturados com sucesso. Triagem processou **567 imagens** e filtrou **66 aprovadas** com **~57 ofertas novas** extraídas.