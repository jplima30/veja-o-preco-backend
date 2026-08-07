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

*Última atualização: 30/07/2026 — Sessão 44: Extração via Canvas HTML5 e Tratamento Preventivo de Popups.*

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

---

**Sessão 22 (Segregação de Relatórios no Terminal e Estatísticas Diárias)**

**Data:** 23 de Junho de 2026
**Objetivo:** Implementar um script local de resumo para as ofertas do dia atual no Firestore e separar as métricas de conversão de imagens entre Sites/E-commerce (200x200 no Storage) e Redes Sociais (ícones padrão).

**Resultados:**
1. **Script de Resumo (`resumo_hoje.py`):** Criação de um utilitário em Python que realiza a busca das ofertas inseridas hoje no Firestore e organiza o relatório final em formato de tabela no terminal.
2. **Segregação de Fontes:** Divisão da saída do relatório em duas categorias claras:
   * **🛍️ CONVERSÃO DE IMAGENS DE SITES / E-COMMERCE:** Produtos que possuem imagens individuais isoladas e que foram otimizadas e cacheadas com sucesso no Firebase Storage (`✅ STORAGE` ou `⚠️ LINK EXTERNO`).
   * **📱 EXTRAÇÕES DE REDES SOCIAIS:** Ofertas lidas de frames do Instagram/Facebook onde imagens individuais de produto não são esperadas (utilizando o status `🎨 ÍCONE APP` por padrão, ou `✅ STORAGE` quando a imagem foi herdada/sincronizada de um cadastro prévio).
3. **Métricas de Operação Divididas:** A taxa de conversão do Storage agora é calculada especificamente sobre as ofertas de sites (onde a conversão de foto é elegível), mantendo 100% de conformidade com os ícones de categorias nas ofertas de redes sociais.
4. **Integração nas Automações:** Adicionado o acionamento do script ao final do `captura_visivel.command` (executado pelo `launchd` local às 10h e 14h) e como uma dica em `rodar_cron_manual.py`.

---

**Sessão 23 (Otimização de Cache e Performance no App)**

**Data:** 30 de Junho de 2026
**Objetivo:** Adicionar cabeçalho de cache HTTP no endpoint principal de consulta de ofertas para otimizar o consumo de leituras no Firestore e banda no Firebase Storage, preparando a infraestrutura para escalas de 100 a 1000 usuários ativos.

**Resultados:**
1. **Cabeçalho de Cache HTTP (`Cache-Control`):** Implementação do cabeçalho `Cache-Control: public, max-age=600` (10 minutos) na resposta JSON da Cloud Function `get_ofertas_do_dia`.
2. **Prevenção de Desperdício de Leituras:** Evita que aberturas repetidas do app iOS pelo mesmo usuário façam requisições repetidas ao Firestore, aproveitando o cache em disco local do celular (iOS URLCache) e economizando até 99% das chamadas em acessos frequentes.
3. **Preparação para Escala:** Garante estabilidade financeira e operacional no plano Blaze do Firebase, mantendo as cotas operacionais seguras e com custo praticamente nulo sob tráfego real.

---

**Sessão 24 (Recorte e Extração Automática de Imagens de Produtos via IA)**

**Data:** 30 de Junho de 2026
**Objetivo:** Implementar o recorte inteligente de fotos de produtos a partir de panfletos e posts de redes sociais compostos. Usar o Gemini 3.1 Flash para extrair a coordenada delimadora `box_2d` e processar a imagem em memória na Cloud Function via `Pillow`.

**Resultados:**
1. **Recorte Inteligente em Memória (`upload_imagem_cortada`):** Criação de um helper que converte coordenadas relativas da IA (0 a 1000) em pixels físicos, executa o crop (recorte), redimensiona para 200x200 pixels, exporta para JPEG (75% de qualidade) e carrega no Firebase Storage.
2. **Atualização das Cloud Functions (`extrair_dados_imagem` e `buscar_encarte_assai`):**
   * Prompts do Gemini atualizados para retornar `"box_2d"` (caixa delimadora justa ao redor do produto físico) e `"quadro_index"` (número identificador do frame ou página do encarte).
   * Lógica do loop de inserção ajustada para realizar o recorte e salvar a imagem individual para cada item extraído das Redes Sociais e do Tabloide Assaí.
3. **Mecanismo de Bypass de Repetição:** Proteção em `salvar_produto_e_oferta` para identificar links de imagem que já estejam no Storage próprio, pulando downloads externos redundantes e otimizando performance.
4. **Validação Local:** Script de teste local com imagem sintética e mocks da API do Storage validou com sucesso as fórmulas matemáticas de mapeamento e a integridade final dos pixels recortados.

---

**Sessão 25 (Rastreabilidade de Imagens e Curação de Catálogo via Script)**

**Data:** 30 de Junho de 2026
**Objetivo:** Implementar o rastreamento da procedência/qualidade das imagens no Firestore (campo `imagem_origem`) e criar um script utilitário interativo para higienização guiada do catálogo de produtos, substituindo recortes temporários de encartes por imagens limpas de alta qualidade de forma semi-automatizada.

**Resultados:**
1. **Rastreabilidade no Firestore (`imagem_origem`):**
   * Adicionada a propriedade `imagem_origem` no documento do produto em `/produtos` com os status: `"auto_crop"` (recorte automático por IA), `"open_food_facts"` (imagem limpa da base livre), `"api_loja"` (imagem oficial da API do mercado), `"manual"` (imagem higienizada pelo desenvolvedor) ou `"padrao"` (sem imagem/ícone).
   * Implementada retrocompatibilidade que promove imagens legadas salvas no Storage para o status `"manual"` por segurança, blindando-as contra sobrescritas automáticas nas rodadas do CRON diário.
2. **Resolução de Distorções (`ImageOps.pad`):**
   * Refatorado o processamento de imagens do helper `upload_imagem_cortada` na Cloud Function para utilizar a função `ImageOps.pad` da biblioteca Pillow, redimensionando as imagens para exatamente `200x200` pixels preservando a proporção original do produto (aspect ratio) e preenchendo as laterais com fundo branco limpo.
3. **Utilitário de Curação (`scripts/central_imagens.py`):**
   * Criação de um script interativo que varre o Firestore em tempo real procurando produtos com imagem pendente ou classificados como `"auto_crop"`.
   * Realiza a consulta automatizada na API do Open Food Facts e, caso encontre uma imagem válida de estúdio, executa a carga no Storage e a atualização no Firestore.
   * Se a busca falhar, interrompe no terminal de forma guiada para que o desenvolvedor cole uma URL do Google Imagens, automatizando o restante do fluxo (download, ajuste de proporção sem distorção, upload no Storage e registro).

---

**Sessão 26 (Refinamento do Script de Higienização e Status de Recortes Aceitos)**

**Data:** 01 de Julho de 2026
**Objetivo:** Refinar o script utilitário `scripts/central_imagens.py` para permitir curadoria seletiva por meio de menus interativos (focando em produtos sem imagem ou recortes específicos) e introduzir a marcação de recortes aceitos (`"auto_crop_aceito"`) para otimizar as tarefas de curadoria.

**Resultados:**
1. **Menu de Execução Seletiva (CLI):** Implementação de menu numérico com 4 opções na inicialização do script:
   * **Opção 1:** Apenas produtos totalmente SEM IMAGEM (Crítico/Urgente).
   * **Opção 2:** Apenas produtos com recortes RECENTES da IA (`auto_crop`).
   * **Opção 3:** Apenas recortes da IA que já foram ACEITOS anteriormente (`auto_crop_aceito`).
   * **Opção 4:** Tudo (Sem imagem + Recortes novos + Recortes aceitos).
2. **Aprovação Manual de Recortes (`auto_crop_aceito`):**
   * Adicionada a opção de tecla **`[A] Aceitar recorte atual`** no fluxo do script. 
   * Caso o usuário decida manter o recorte automático da IA, o script altera a `imagem_origem` do produto para `"auto_crop_aceito"` no Firestore.
   * Isso remove o produto das filas cotidianas (Opções 1 e 2) nas próximas execuções do script, preservando a rastreabilidade caso o desenvolvedor decida revisá-las no futuro (Opção 3).
3. **Resiliência e Retentativa de Erros:**
   * Corrigido o bug de NameError (`name 'datetime' is not defined`) importando a classe `datetime` no cabeçalho do script.
   * Implementado um loop de retentativa guiada (`while True`) ao redor do fluxo de processamento de cada produto. Caso ocorra um erro de download ou processamento, o script exibe o erro e permite escolher entre retentar (digitar outra URL) ou pular, evitando pulos automáticos por falhas de link ou conexão.
4. **Contexto de Supermercados:**
   * Adicionada a consulta sob demanda à coleção `/ofertas` para identificar e listar quais supermercados possuem ofertas ativas para o produto que está sendo analisado, exibindo a informação (ex: `🛒 Supermercado(s): Assaí Atacadista`) no painel de curadoria do terminal.

---

**Sessão 27 (Unificação de Unidades no Firestore e Mesclagem de Duplicados)**

**Data:** 01 de Julho de 2026
**Objetivo:** Implementar padronização automática de unidades de medida (como `un`/`cada` e `kg`/`quilo`) no backend para evitar novos produtos duplicados no Firestore. Criar e executar um script de migração em lote para mesclar os históricos de ofertas e deletar cadastros duplicados existentes. Adicionar a opção "Piloto Automático" de lote no script de curadoria.

**Resultados:**
1. **Unificação de Unidades no Backend (`normalizar_unidade`):**
   * Implementada a função `normalizar_unidade` em [functions/main.py](file:///Users/jplima/Documents/veja-o-preco-backend/functions/main.py#L47-L61) que unifica strings de medida: `cada`/`unidade`/`und`/`unid` viram `"un"`; `quilo`/`kilo` viram `"kg"`; `litro`/`litros` viram `"l"`; e `grama`/`gramas`/`gr` viram `"g"`.
   * Integrada a normalização em `normalizar_nome` e `salvar_produto_e_oferta`, garantindo que novos anúncios de diferentes mercados mapeiem para o mesmo ID único e usem a mesma unidade padronizada no Firestore.
2. **Script de Mesclagem em Lote (`scripts/mesclar_produtos.py`):**
   * Desenvolvido e executado utilitário de migração no banco de dados. Ele identificou 219 produtos duplicados no Firestore.
   * O script atualizou e redirecionou com sucesso 71 ofertas ativas ligadas aos IDs antigos para os IDs principais normalizados, e removeu 219 cadastros duplicados do banco. Também garantiu herança automática de imagens caso o cadastro secundário possuísse foto e o principal não.
3. **Modo Piloto Automático (Opção 5):**
   * Adicionada a opção `[5] Piloto Automático` ao menu inicial de [central_imagens.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/central_imagens.py).
   * Este modo analisa em lote os produtos sem fotos ou com recortes e consulta o Open Food Facts de forma 100% automatizada e silenciosa. Se encontrar a foto, otimiza e faz o upload; se não encontrar, apenas avança instantaneamente para o próximo, eliminando interações repetitivas.
4. **Integração com DuckDuckGo Images como Fallback:**
   * Desenvolvida a função `buscar_duckduckgo_images` para pesquisar imagens de produtos via DuckDuckGo de forma gratuita, limpa e sem limite restritivo de taxa.
   * O fluxo limpa termos extras do nome do produto (como `(un)`, `(kg)`) para aumentar a precisão da busca.
   * Integrado no loop de curação: caso o Open Food Facts não encontre a imagem, o DuckDuckGo é consultado automaticamente.
   * No modo interativo, o usuário pode aprovar com `[Y]` ou pular. No piloto automático (`Opção 5`), o script adota a imagem do DuckDuckGo de forma 100% automatizada caso o OFF falhe.

---

**Sessão 28 (Busca Exclusiva via DuckDuckGo com Coleta e Download Resiliente de Multi-Links)**

**Data:** 01 de Julho de 2026
**Objetivo:** Remover a dependência do Open Food Facts devido a lentidões e limites de taxa de IP (erros 503). Tornar o DuckDuckGo Images o mecanismo de busca primário e único. Aumentar a resiliência de downloads contra bloqueios (HTTP 403) e links quebrados (HTTP 404) implementando tentativas sequenciais de múltiplos links.

**Resultados:**
1. **Remoção do Open Food Facts:**
   * A função `buscar_open_food_facts` e todos os tempos de espera de 6 segundos associados foram removidos do script [central_imagens.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/central_imagens.py), tornando a varredura instantânea.
2. **DuckDuckGo como Motor Exclusivo com Multi-Links:**
   * A função `buscar_duckduckgo_images` foi reconfigurada para retornar uma lista com os **top 4 links** de imagens para cada produto.
3. **Fluxo de Download Resiliente:**
   * O loop principal do script agora testa sequencialmente cada uma das 4 URLs retornadas. Caso o primeiro link falhe com erro HTTP 403 (bloqueio do servidor de origem) ou HTTP 404 (link quebrado), o script avança automaticamente para o próximo link.
   * O produto só é pulado ou encaminhado para a entrada manual se todas as 4 tentativas de download falharem, garantindo máxima automação no Piloto Automático (Opção 5).

---

**Sessão 29 (Sincronização de Imagens para Ofertas e Refinamento de Duplicados)**

**Data:** 01 de Julho de 2026
**Objetivo:** Ajustar as normalizações de ID de produto para filtrar sufixos de unidade presentes no final do nome dos produtos enviados pelos scrapers (ex: `"ACÉM COM OSSO KG"`). Criar um script utilitário para sincronizar as imagens dos produtos curados nas ofertas ativas correspondentes.

**Resultados:**
1. **Filtro de Unidade Redundante no Nome (main.py):**
   * Modificada a função `normalizar_nome` em [functions/main.py](file:///Users/jplima/Documents/veja-o-preco-backend/functions/main.py#L62-L77) para remover qualquer sufixo redundante de unidade do final do nome (`kg`, `quilo`, `un`, `cada`, `g`, etc.) usando expressões regulares antes de aplicar a concatenação do ID.
2. **Reconfiguração do Mesclador (`scripts/mesclar_produtos.py`):**
   * Replicada a mesma regex de limpeza de sufixo redundante no gerador de ID interno do script de mesclagem, permitindo que produtos como `acem-com-osso-resfriado-bovino-kg-quilo` agrupem-se e sejam consolidados sob o ID correto `acem-com-osso-resfriado-bovino-kg`.
3. **Novo Script de Sincronização (`scripts/sincronizar_imagens_ofertas.py`):**
   * Desenvolvido script para varrer todas as ofertas do Firestore e atualizar o campo `imagem_url` com a URL curada do produto correspondente, propagando as imagens de estúdio para a tela do iOS App.
4. **Deploy de Cloud Functions:**
   * Implantadas as Cloud Functions (`buscar_encarte_assai`, `extrair_dados_imagem`) com a nova lógica de ID refinada.

---

**Sessão 30 (Automação da Curadoria e Sincronização de Imagens no Cron)**

**Data:** 02 de Julho de 2026
**Objetivo:** Automatizar por completo o fluxo de curadoria e sincronização de imagens, integrando-os diretamente ao final do fluxo do Cron do Playwright (rodando às 10h e 14h) para que novas ofertas sejam curadas e sincronizadas imediatamente sem intervenção manual. Criar o arquivo de workflow local `/fluxo`.

**Resultados:**
1. **Suporte a Argumentos na Central (`central_imagens.py`):**
   * Adicionada a leitura do argumento de terminal `--autopilot` (ou `--piloto`) para que o script ignore o menu interativo e selecione automaticamente o modo `[5] PILOTO AUTOMÁTICO`.
2. **Integração no Fluxo de Cron (`scripts/cron_playwright.py`):**
   * Configurado o script principal do Cron do Playwright para disparar a Central de Imagens (`central_imagens.py --cron-completo`) assim que a triagem de ofertas e gravação no Firestore se completarem com sucesso.
   * Corrigido o interpretador Python usado no Cron para apontar explicitamente para o ambiente de backend (`functions/venv/bin/python3`) em vez de `sys.executable`, eliminando erros de importação do Firebase Admin (`ModuleNotFoundError`).
3. **Criação do Workflow de Desenvolvimento (`.agents/workflows/fluxo.md`):**
   * Desenvolvido e documentado o workflow local `/fluxo` mapeando os passos completos de gestão de projeto (GitHub Issues), Git Flow (`develop` ➡️ `main` com `--no-ff`), atualização de documentações e travas de segurança/permissão para o Deploy do Firebase.
4. **Filtro de Slogans Promocionais (functions/main.py & scripts/mesclar_produtos.py):**
   * Criada a função `limpar_nome_promocional` que limpa slogans do tipo `"Leve mais e pague menos"`, `"Leve X pague Y"`, etc. dos nomes dos produtos antes de salvar no Firestore, padronizando a nomenclatura e prevenindo duplicatas.
5. **Modo Manual em `scripts/mesclar_produtos.py`:**
   * Adicionado suporte a parâmetros `--de` e `--para` no script de mesclagem para viabilizar a consolidação cirúrgica de IDs arbitrários com erros de digitação (como `"INTTIMUS"` para `"INTIMUS"`).
6. **Suporte a Imagens Locais (Drag-and-Drop) na Central:**
   * Adicionado suporte a arquivos locais em `processar_e_otimizar_imagem`. O usuário pode arrastar um arquivo direto do PC para o terminal (que insere o caminho local absoluto), o script lê a foto do disco, otimiza e faz o upload para o Firebase Storage perfeitamente.

---

**Sessão 31 (Painel de Controle Unificado)**

**Data:** 02 de Julho de 2026
**Objetivo:** Consolidar a operação local do backend desenvolvendo uma interface unificada que integre todos os 24 scripts utilitários do repositório em uma única entrada, facilitando a execução e automatizando a ativação dos ambientes virtuais correspondentes (venv).

### Implementações:
1. **Painel de Controle CLI (`scripts/gerenciador.py`):**
   * Desenvolvido um script gerenciador interativo escrito em Python puro (sem dependências externas de pacotes adicionais para execução da interface).
   * Organizados os scripts locais do repositório em 6 submenus categorizados por responsabilidade: Coleta & Scrapers, Triagem & OCR, Conectores de Lojas, Curação & Higienização, Diagnósticos & Relatórios e Testes.
2. **Roteamento Inteligente de Ambientes Virtuais (Venvs):**
   * O painel detecta automaticamente se o script pertence à camada de OCR/Triagem (`venv_triagem/bin/python3`) ou de nuvem/banco/Firebase (`functions/venv/bin/python3`).
   * Elimina a necessidade de o operador ativar manualmente os ambientes via `source venv/.../activate` no Terminal.
3. **Passagem de Parâmetros e Interatividade:**
   * Scripts que exigem parâmetros (ex: mesclador de produtos manual) solicitam a digitação dos argumentos (como ID de origem e ID de destino) interativamente no próprio painel antes da chamada do subprocesso.
   * Adicionada visualização rápida de logs (`ver_log(log_name)`) exibindo as últimas 50 linhas de relatórios do cron diretamente na tela de forma otimizada.

---

**Sessão 32 (Fuzzy Matching e Diagnóstico de Duplicatas no Cron)**

**Data:** 02 de Julho de 2026
**Objetivo:** Implementar um mecanismo inteligente de busca por similaridade de texto no Firestore para detectar e relatar possíveis duplicatas causadas por erros ortográficos de leitura (OCR/IA) ou diferença na ordem de palavras, alertando o operador de forma silenciosa na execução do Cron e disponibilizando um assistente interativo para mesclagens direcionadas.

### Implementações:
1. **Script Fuzzy de Duplicatas (`scripts/identificar_duplicatas.py`):**
   * Desenvolvido algoritmo de correspondência usando a biblioteca nativa `difflib`. Combina similaridade direta (erros de escrita), similaridade por token sort (inversão na ordem de palavras) e análise de overlap de termos.
   * Otimizado o processamento com precomputação de dados e heurística de correspondência numérica, reduzindo a complexidade de loops e o volume de falsos positivos em nomes curtos (ex: impede casamento incorreto de "Alho" e "Alho Roxo").
2. **Integração Silenciosa no Final do Cron (`cron_playwright.py`):**
   * Configurado o cron para disparar `identificar_duplicatas.py --detect-only` logo após as rotinas de curadoria automática de imagens.
   * O script analisa a base e imprime um bloco informativo com as top 10 potenciais duplicatas nos logs diários de forma 100% não-bloqueante (sem parar o script).
3. **Assistente Interativo no Painel de Controle (`gerenciador.py`):**
   * Adicionado o assistente interativo na Categoria 4 como opção `[4] Assistente de Duplicatas Inteligente (Fuzzy Matching)`.
   * Permite revisar os potenciais duplicados um por um na tela do terminal exibindo links clickáveis das fotos e scores separados (Similaridade e Overlap).
4. **Mesclagem Automática por Ordem de Palavras:**
   * Implementada a opção `[4]` no assistente interativo para mesclagem automática em lote de palavras 100% idênticas (`w1 == w2`).
5. **Sistema Dinâmico de Sinônimos/Aliases (Firestore):**
   * Criada a coleção `/sinonimos` no Firestore. Ao mesclar/deletar qualquer duplicata B em A, grava-se o redirecionamento `B ➡️ A`.
   * O Cloud Functions (`functions/main.py`) intercepta todas as inserções/lotes e desvia o tráfego do ID duplicado para o ID correto em tempo real. O banco "aprende" e impede re-ingestão de duplicidades.

---

**Sessão 33 (Filtro Permanente de Falsos Positivos de Duplicatas)**

**Data:** 03 de Julho de 2026
**Objetivo:** Implementar um mecanismo para que decisões de "Ignorar" (Opção 3) no assistente interativo de duplicatas sejam persistidas permanentemente no Firestore, evitando que produtos parecidos mas legítimos fiquem reaparecendo nas próximas varreduras do assistente ou nos relatórios diários do Cron.

### Implementações:
1. **Coleção de Blacklist no Firestore (`duplicatas_ignoradas`):**
   * Criada a coleção `/duplicatas_ignoradas` no Firestore para armazenar chaves exclusivas de pares de IDs de produtos legítimos desconsiderados (chave formada por `id_menor_vs_id_maior`).
2. **Atualização do Assistente CLI (`scripts/identificar_duplicatas.py`):**
   * Configurada a opção `[3] Ignorar` no assistente interativo para salvar o par de produtos ignorados na coleção `/duplicatas_ignoradas` em tempo real.
3. **Integração no Escaneador Geral:**
   * Atualizada a função `buscar_duplicatas_potenciais()` para carregar todas as chaves ignoradas no início do processo e filtrá-las do loop de similaridades. Isso impede que os falsos positivos apareçam tanto no painel interativo quanto nos alertas silenciosos do Cron diário.

---

**Sessão 34 (Controle de Popups do Instagram no Playwright)**

**Data:** 03 de Julho de 2026
**Objetivo:** Resolver erros de captura de frames de vídeo (Timeouts de screenshots) causados por overlays/popups de geolocalização e notificações que o Instagram exibe durante as navegações automáticas do Cron.

### Implementações:
1. **Auto-concessão de Permissões no Playwright:**
   * Injetado o parâmetro `permissions=["geolocation", "notifications"]` na inicialização do navegador persistente (`launch_persistent_context`) e na criação de contexto temporário fallback (`new_context`). Isso faz com que o Chromium conceda automaticamente essas permissões no nível de sistema operacional sem levantar popups visuais.
2. **Helper de Modais Web (`tratar_popups_instagram`):**
   * Desenvolvida a função `tratar_popups_instagram(page)` no script `cron_playwright.py` para fechar modais HTML e overlays que aparecem durante o aquecimento da home do Instagram e após abrir perfis de lojas. Ela detecta e clica em botões de dispersão/fechamento (ex: `"Agora não"`, `"Cancelar"`, `"Não permitir"`, `"Permitir"`, `"Not now"`).
3. **Resiliência do Crawler:**
   * Com os popups contidos e fechados de forma proativa, os elementos de vídeo e posts ficam totalmente desimpedidos na tela, eliminando as falhas de timeouts nas capturas de tela dos frames para triagem OCR.

---

**Sessão 35 (Refatoração de Categorias e Migração de Catálogo)**

**Data:** 03 de Julho de 2026
**Objetivo:** Implementar normalização de categorias no backend (unificando e mapeando nomenclaturas proprietárias e produtos de rotisseria/lanchonete) e realizar a migração em lote de todos os produtos (1.645) e ofertas ativas (520) no Firestore para as novas categorias do app.

### Implementações:
1. **Normalizador de Categorias (`normalizar_categoria`):**
   * Desenvolvida a função `normalizar_categoria(categoria)` no [functions/main.py](file:///Users/jplima/Documents/veja-o-preco-backend/functions/main.py) com lógica de casamento de palavras inteiras (regex `\b`) e exclusões para produtos industrializados/processados (como farofa e extrato).
   * Mapeadas as novas categorias do app: `ALIMENTOS`, `CARNES`, `HORTIFRUTI`, `PADARIA`, `BEBIDAS`, `HIGIENE`, `LIMPEZA` (direcionando lanchonete/rotisseria para `PADARIA`).
2. **Atualização de Prompts do Gemini:**
   * Atualizados os prompts de extração de PDF (Mateus/Assaí) e Visão (Instagram) no `main.py` para classificar os produtos diretamente nas 7 novas categorias.
3. **Script de Migração do Firestore (`scripts/reclassificar_categorias.py`):**
   * Criado utilitário de migração em lote com `WriteBatch` do Firestore. O script processou e atualizou 1.645 produtos e as ofertas ativas no banco de dados com 100% de sucesso.

---

**Sessão 36 (Assistente de Auditoria de Categorias e Integração no Cron)**

**Data:** 03 de Julho de 2026
**Objetivo:** Desenvolver uma ferramenta de auditoria semântica de categorias ("pente fino") utilizando inteligência artificial em lote (Gemini 3.1 Flash Lite) para revisar produtos que caíram no fallback de `ALIMENTOS`, integrar a verificação de forma silenciosa no final da execução diária do Cron, e adicionar a interface interativa no painel gerenciador.

### Implementações:
1. **Script de Auditoria Inteligente (`scripts/auditar_categorias.py`):**
   * Desenvolvido script que consome lotes de até 100 produtos da categoria `ALIMENTOS` e os envia para o Gemini 3.1 Flash Lite revisar se pertencem semanticamente a categorias mais específicas (`CARNES`, `HORTIFRUTI`, `BEBIDAS`, `PADARIA`, `HIGIENE`, `LIMPEZA`).
   * Adicionado suporte a chaves dinâmicas recuperadas diretamente do GCP Secret Manager via CLI `gcloud secrets` caso a chave local não esteja no ambiente.
   * Modos: Interativo (correção com escolhas no console) e `--detect-only` (silencioso para logs).
2. **Integração no Cron Diário (`scripts/cron_playwright.py`):**
   * Configurada a execução de `auditar_categorias.py --detect-only` no bloco final do Cron de captação de ofertas. Isso gera alertas automáticos de suspeitas de categorização nos logs diários.
3. **Integração no Gerenciador (`scripts/gerenciador.py`):**
   * Adicionada a opção `[6] Assistente de Auditoria de Categorias` no submenu de Curadoria e Higienização, permitindo a limpeza interativa manual das suspeitas geradas pelo Cron.

---

**Sessão 37 (Enriquecimento da Documentação Operacional e Comandos de Deploy)**

**Data:** 06 de Julho de 2026
**Objetivo:** Ampliar a documentação do projeto detalhando a estrutura das 6 categorias do painel de controle CLI (`gerenciador.py`) e adicionando instruções claras de deploy para as Cloud Functions na nuvem, tanto completas quanto cirúrgicas (individuais).

### Implementações:
1. **Manual da Wiki ([Operacao-Local.md](file:///Users/jplima/Documents/veja-o-preco-backend/wiki-repo/Operacao-Local.md)):**
   * Detalhamento de todas as abas e funções do gerenciador CLI.
   * Criação da seção 7 dedicada ao deploy via Firebase CLI com comandos rápidos e boas práticas.
2. **README do Projeto ([README.md](file:///Users/jplima/Documents/veja-o-preco-backend/README.md)):**
   * Reorganização da seção "Operação e Testes" para evidenciar a estrutura das 6 abas do gerenciador.
   * Adicionado o guia de deploy cirúrgico de Cloud Functions na nuvem.
3. **Página Inicial ([Home.md](file:///Users/jplima/Documents/veja-o-preco-backend/wiki-repo/Home.md)):**
   * Ajuste das seções de início rápido para recomendar o uso primário de `gerenciador.py`.

---

**Sessão 38 (Criação da Categoria Frios e Laticínios e Migração do Banco)**

**Data:** 06 de Julho de 2026
**Objetivo:** Introduzir a nova categoria `FRIOS_LATICINIOS` no ecossistema (backend e banco de dados) para reclassificar de forma precisa leite, queijos, presuntos, manteigas, margarinas e iogurtes, eliminando falsos positivos nas seções de `HORTIFRUTI` e `CARNES`.

### Implementações:
1. **Normalização no Backend ([main.py](file:///Users/jplima/Documents/veja-o-preco-backend/functions/main.py)):**
   * Adicionada a regra de detecção e normalização para `FRIOS_LATICINIOS` na função `normalizar_categoria` antes de carnes/hortifruti.
   * Implementadas travas de segurança contra falsos positivos (ex: impede que chocolates e biscoitos "ao leite" virem laticínios).
   * Removidos termos redundantes como `presunto`, `mortadela` e `salame` de `termos_carnes`.
   * Atualizados os prompts de visão e PDF do Gemini para classificar itens entre as 8 categorias oficiais.
2. **Auditoria de Categorias ([auditar_categorias.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/auditar_categorias.py)):**
   * Adicionado suporte para sugerir e aceitar a categoria `FRIOS_LATICINIOS`.
3. **Script de Migração em Lote ([reclassificar_frios_laticinios.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/reclassificar_frios_laticinios.py)):**
   * Desenvolvido script de migração do banco Firestore. O script processou e atualizou em lote **204 produtos** e **94 ofertas ativas** vinculadas.
4. **Contrato de Dados:**
   * Atualizado o contrato de dados local ([CONTRATO_DADOS_PADRAO.md](file:///Users/jplima/Documents/veja-o-preco-backend/docs/CONTRATO_DADOS_PADRAO.md)) e na wiki ([Contrato-de-Dados.md](file:///Users/jplima/Documents/veja-o-preco-backend/wiki-repo/Contrato-de-Dados.md)) registrando os 8 grupos.

---

**Sessão 39 (Criação da Categoria PET e Migração do Banco)**

**Data:** 06 de Julho de 2026
**Objetivo:** Adicionar a 9ª categoria oficial do ecossistema, `PET` (Produtos para Animais de Estimação), para isolar de forma correta rações, petiscos e itens de higiene/limpeza veterinária, eliminando falsos positivos nas seções de `ALIMENTOS`, `CARNES` e `HIGIENE` humana.

### Implementações:
1. **Normalização no Backend ([main.py](file:///Users/jplima/Documents/veja-o-preco-backend/functions/main.py)):**
   * Adicionado o bloco de checagem da categoria `PET` no início de `normalizar_categoria` com limite de palavras seguras.
   * Removidas as palavras-chaves de ração da lista de exclusão genérica que forçava desvio para `ALIMENTOS`.
   * Atualizados os prompts de visão e extração de PDF no Gemini para aceitar e extrair itens sob a categoria `PET`.
2. **Auditoria de Categorias ([auditar_categorias.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/auditar_categorias.py)):**
   * Incluído suporte para classificar itens manualmente e propor sugestões para `PET`.
3. **Script de Migração em Lote ([reclassificar_pets.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/reclassificar_pets.py)):**
   * Desenvolvido e executado o script de migração no Firestore, resultando na reclassificação de **43 produtos** e **15 ofertas ativas** para a categoria `PET`.
4. **Contrato de Dados:**
   * Atualizado o contrato de dados local ([CONTRATO_DADOS_PADRAO.md](file:///Users/jplima/Documents/veja-o-preco-backend/docs/CONTRATO_DADOS_PADRAO.md)) e na wiki ([Contrato-de-Dados.md](file:///Users/jplima/Documents/veja-o-preco-backend/wiki-repo/Contrato-de-Dados.md)) para constar os 9 grupos oficiais.

---

**Sessão 40 (Automatização e Trava de Segurança da Auditoria de Categorias)**

**Data:** 06 de Julho de 2026
**Objetivo:** Automatizar a curadoria e correção semântica de categorias no Cron diário, implementando travas rígidas de validação de categorias, filtros de coerência (evitando desvios de doces para bebidas) e um coletor de lixo inteligente (`EXCLUIR`) para remover itens inválidos do Firestore, protegendo também as Cestas Básicas.

### Implementações:
1. **Auditoria Automática (`--auto-apply`):**
   * Adicionado o modo `--auto-apply` no script [auditar_categorias.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/auditar_categorias.py) para reclassificar ou excluir produtos e ofertas de forma automática e silenciosa.
   * Modificado o script de Cron [cron_playwright.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/cron_playwright.py) para disparar o script de auditoria com `--auto-apply` ao término das capturas diárias.
2. **Travas de Validação e Segurança (Python):**
   * **Validação de Whitelist:** Descarte imediato de qualquer sugestão fora das 8 categorias oficiais do App, impedindo salvamento de tags inexistentes como `OUTROS`.
   * **Bloqueio de Coerência de Doces:** Travas em código que impedem a reclassificação de caixas de bombom, chocolates e biscoitos para `BEBIDAS` ou `CARNES`.
   * **Proteção de Cesta Básica:** Travas de segurança baseadas em palavras-chaves que proíbem que produtos contendo "cesta básica" ou "cesta basica" sejam deletados ou movidos. Elas permanecem em `ALIMENTOS`.
3. **Coletor de Lixo Inteligente (`EXCLUIR`):**
   * Instruído o Gemini a sugerir o termo `EXCLUIR` para itens de bazar (móveis, roupas, eletrônicos, etc.) que vazaram no scanner. Quando identificado, o script realiza a deleção do produto e de suas ofertas vinculadas no Firestore.

---

**Sessão 41 (Ingredientes Regionais e Central de Imagens Híbrida)**

**Data:** 07 de Julho de 2026
**Objetivo:** Adicionar inteligência nativa para ingredientes regionais do Norte (jambu, maniva, mandioca e macaxeira) na categorização estática das Cloud Functions e aprimorar a Central de Imagens para resolver links externos de imagem quebrados (VIP Commerce) com curadoria híbrida (interativa/piloto automático) e curadoria individual por ID do produto.

### Implementações:
1. **Regras Regionais de Hortifrúti ([main.py](file:///Users/jplima/Documents/veja-o-preco-backend/functions/main.py)):**
   * Adicionadas as palavras-chaves `"maniva"`, `"jambu"`, `"mandioca"` e `"macaxeira"` na lista de termos estáticos de `HORTIFRUTI` da função `normalizar_categoria`.
   * Realizado o deploy atualizado de todas as Cloud Functions.
2. **Central de Imagens Híbrida ([central_imagens.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/central_imagens.py)):**
   * **Expansão da Opção 3:** Renomeada para cobrir tanto recortes aceitos (`auto_crop_aceito`) quanto imagens externas de APIs de Lojas (`api_loja` com links externos da VIP Commerce), permitindo limpar links quebrados da base.
   * **Modo Híbrido por Lote:** Ao iniciar a Opção 3, o script permite escolher entre curar interativamente (1 por 1) ou disparar o piloto automático silencioso específico para este grupo de imagens.
   * **Mapeamento de Estatísticas:** Ajustado o cálculo do painel para incluir as imagens externas de APIs no grupo de recortes/pendências a revisar.
   * **Opção 8 (Curar por ID específico):** Adicionado suporte para curar um produto específico digitando seu ID de produto ou o ID de documento de sua oferta. Se o ID inserido corresponder a uma oferta ativa, o script resolve e curadoriza automaticamente o produto associado.
   * **Unificação de Imagens Externas:** Atualizadas as opções **1 (Sem Foto)** e **5 (Piloto Automático)** para detectar e curar nativamente qualquer produto que use uma URL de imagem externa que não esteja hospedada no Storage do Firebase.
   * **Alerta de Pendências de Imagem Externa:** Acrescentada uma varredura pós-sincronização em `executar_sincronizacao` que exibe no terminal local (e nos logs do Cron) um aviso/alerta se houver alguma oferta ativa apontando para links externos de lojas.
3. **Otimização de Sequência do Cron ([cron_playwright.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/cron_playwright.py)):**
   * Reordenada a fila de scripts de pós-triagem para rodar o auditor de categorias (`auditar_categorias.py --auto-apply`) **antes** da central de imagens (`central_imagens.py --cron-completo`).
   * Isso evita o processamento de curadoria automática (busca DuckDuckGo e download) para produtos inválidos (bazar/lixo) que seriam deletados em seguida pela auditoria.

---

**Sessão 42 (Deduplicação Automática e Visibilidade de Lojas)**

**Data:** 08 de Julho de 2026
**Objetivo:** Automatizar a mesclagem de produtos duplicados com nomes 100% idênticos diretamente no fluxo do Cron e melhorar a tomada de decisão no assistente interativo de duplicatas exibindo quais supermercados possuem ofertas ativas para cada ID comparado.

### Implementações:
1. **Deduplicação Inteligente no Cron ([cron_playwright.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/cron_playwright.py)):**
   * Modificada a rotina de pós-captura para disparar o script de duplicatas com a nova flag silenciosa `--auto-merge-exact-words-silent` antes de exibir o diagnóstico de detecção `--detect-only`.
   * Com isso, o Cron resolve e mescla automaticamente todas as duplicidades óbvias de nomes idênticos no Firestore a cada rodada das 10h e 14h, deixando no log final apenas os conflitos complexos que exigem decisão humana.
2. **Flag de Mesclagem Silenciosa ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Inserido o suporte à flag `--auto-merge-exact-words-silent` na função `rodar_mesclagem_automatica_exata` para pular o bloqueio de confirmação `input()` ao rodar no Cron ou em segundo plano.
3. **Visibilidade de Supermercados Ativos e Históricos ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionada busca em tempo real na coleção de `/ofertas` para os IDs comparados.
   * **Tratamento de Visão (IA):** Criado o dicionário `MAP_SUPERMERCADOS` para mapear o `supermercado_id` (ex: `formosa` -> `Formosa`) caso o campo `loja` venha preenchido com a string genérica da extração via visão computacional.
   * **Fallback de Histórico:** Se não houver ofertas vigentes para o produto hoje, o script resgata as ofertas expiradas daquele dia que ainda restam no banco e exibe com a marcação `(Histórico)`.
   * **Fallback de Origem Definitiva:** Se o banco já tiver passado pela faxina noturna do Cron e não tiver nenhuma oferta recente, o assistente lê o campo permanente `supermercado_origem` no cadastro do produto (exibindo `[Sem ofertas] (Origem: Assaí)`).
4. **Certidão de Nascimento do Produto ([main.py](file:///Users/jplima/Documents/veja-o-preco-backend/functions/main.py)):**
   * Ao criar um novo produto em `salvar_produto_e_oferta`, adicionamos o campo permanente `"supermercado_origem": supermercado_id`. Isso garante a identificação da procedência original do produto mesmo após a limpeza de suas ofertas expiradas.

---

**Sessão 43 (Captura Resiliente de Vídeo no Instagram)**

**Data:** 12 de Julho de 2026
**Objetivo:** Solucionar falhas de timeout (30s) na captura de frames de vídeos no Instagram (especialmente no perfil do Assaí) provocadas por overlays transparentes e stickers interativos sobre o elemento de vídeo.

### Implementações:
3. **Captura por Coordenadas (Clip) ([cron_playwright.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/cron_playwright.py)):**
   * Substituída a chamada `video_element.screenshot()` por uma captura recortada na página (`page.screenshot(clip=box, timeout=8000)`).
   * O script agora lê a bounding box do vídeo e faz o print da viewport recortando apenas aquela área geométrica.
   * Isso ignora completamente overlays, stickers ou animações de CSS do Instagram que travavam a estabilização do localizador do Playwright, garantindo a extração rápida de frames e eliminando o timeout de 30s.
   * Mantivemos a triagem local e filtros de custo (OCR) 100% inalterados, preservando a lógica de economia do Gemini Vision.

---

**Sessão 44 (Extração via Canvas HTML5 e Tratamento Preventivo de Popups)**

**Data:** 30 de Julho de 2026
**Objetivo:** Eliminar timeouts no `page.screenshot` durante a captura de vídeos (Reels) no Instagram através da extração direta do buffer de vídeo via HTML5 Canvas em JavaScript e aprimoramento do fechamento de popups de segurança.

### Implementações:
1. **Extração de Frames via HTML5 Canvas ([cron_playwright.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/cron_playwright.py)):**
   * Injetado código JS via `page.evaluate()` que desenha o frame do elemento `<video>` em um `<canvas>` 2D em memória e retorna a imagem Base64 (`canvas.toDataURL('image/jpeg', 0.75)`).
   * Essa chamada roda em menos de 10ms e não depende do engine de screenshot do Playwright, ficando 100% imune a timeouts provocados por animações, overlays ou buscas de buffer no player.
   * Mantido fallback secundário para `page.screenshot(clip=box, animations="disabled", timeout=3000)` caso a segurança do navegador restrinja o Canvas.
2. **Ampliação do Fechador de Popups (`tratar_popups_instagram` em [cron_playwright.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/cron_playwright.py)):**
   * Adicionados novos seletores (ex: `button:has-text('Fechar')`, `button:has-text('Dismiss')`, `svg[aria-label='Fechar']`) para dispensar automaticamente modais de cookies, notificações e janelas suspensas no Instagram.

---

**Sessão 45 (Smart Auto-Merge & Smart Auto-Ignore de Duplicatas no CRON - Issue #45)**

**Data:** 03 de Agosto de 2026
**Objetivo:** Automatizar completamente a triagem e resolução de conflitos de duplicatas no Firestore, eliminando o acúmulo de duplicidades (177 conflitos) através do Smart Auto-Merge de alta confiança e do Smart Auto-Ignore autônomo para variações de sabores e tipos.

### Implementações:
1. **Dicionários Especializados de Catálogo ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Incorporados dicionários especializados mapeados da base do Firestore: `STOPWORDS_QUALIFICADORES` (termos como *original, tradicional, sachê, pacote, caixeta, congelado, resfriado, cumbuca, barra, flocão*), `MAPEAMENTO_ORTOGRAFICO` (mussarela ↔ muçarela, aerosol ↔ aerossol, amazon ↔ amazônia), `TERMOS_VARIACAO_AGRUPADA` (sabores, tipos, variações, diversos, eucalipto, pro, clinical, profissional, bacon, frutas) e discriminadores de SKU.
   * **Expansão de Marcas e Cortes:** Incluídas mais de 50 marcas regionais e de catálogo (`casaredo`, `araguaia`, `ricosa`, `elseve`, `seda`, `target`, `nutrivita`, `dona clara`, `jaguá`, `tchê`, `paladori`, `red horse`, `piramutaba`, `abc`, `concórdia`, `soya`, `vicente`, `belunno`, `camponesa`, `petruz`, `pinho sol`, `doritos`, `yokitos`, `sococo`, `rancheiro`, `zilmar`, `deleyda`, `jundiaí`) e unificação automática de números com unidades (ex: `200 g` ➡️ `200g`).
2. **Algoritmos de Decisão Inteligente ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * **`eh_duplicata_alta_confianca()`:** Identifica duplicatas reais com gramatura idêntica ignorando ruídos de embalagem/ortografia e dispara a mesclagem automática.
   * **`eh_variacao_agrupada()`:** Detecta ofertas genéricas agrupadas vs SKUs específicos e salva o par automaticamente na coleção `/duplicatas_ignoradas` no Firestore de forma não-bloqueante.
   * **`escolher_produto_canonico()`:** Prioriza a manutenção do produto com imagem auditada e/ou maior histórico de ofertas ativas.
3. **Menu Interativo e Execução no CRON:**
   * Adicionada a opção `[5] 🚀 Smart Auto-Merge & Auto-Ignore` no assistente interativo do `gerenciador.py`.
   * Atualizado o `cron_playwright.py` para executar a flag silenciosa `--auto-merge-smart-silent` diariamente no encerramento da captura.

---

**Sessão 46 (Refinamento de Modelos de Fralda e Submarcas no Algoritmo de Deduplicação - Issue #42)**

**Data:** 04 de Agosto de 2026
**Objetivo:** Evoluir a inteligência do algoritmo de deduplicação em `scripts/identificar_duplicatas.py` para eliminar falsos positivos de marcas/modelos específicos (ex: fraldas shortinho/roupinha vs fraldas de fita, e linhas infantis/submarcas como Seda Juntinhos) e realizar mesclagem orientada no Firestore.

### Implementações:
1. **Modelos de Fraldas e Submarcas ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionada a regra de `PROPRIEDADES_INCOMPATIVEIS` para modelos de fralda: `({"shortinho", "roupinha", "pants", "calça"}, {"regular", "tradicional", "fita"})`.
   * Adicionadas submarcas e termos de modelos (`juntinhos`, `shortinho`, `roupinha`, `pants`, `calça`) ao dicionário `TERMOS_VARIACAO_AGRUPADA`, garantindo que produtos de linhas específicas não sejam erroneamente mesclados com produtos regulares.
2. **Mesclagem no Firestore:**
   * Executada com sucesso a mesclagem das ofertas do produto com ruído de OCR (`shampoo-ou-shampoo-condicionador-procao-para-caes-varios-tipos-500ml-un`) para o produto canônico (`shampoo-ou-condicionador-procao-varios-tipos-500ml-un`), registrando o sinônimo de redirecionamento.

---

**Sessão 47 (Expansão de Marcas e Sub-Linhas no Algoritmo de Deduplicação - Issue #43)**

**Data:** 04 de Agosto de 2026
**Objetivo:** Adicionar novas marcas de molho de tomate (`Pomodoro`), qualificadores de sub-linhas/laticínios/peixes (`crocks`, `leve`, `com pele`, `sem pele`) e tamanhos de fralda (`p`, `m`, `g`, `xg`, `xxg`, `xxgg`) para garantir a diferenciação autônoma no `identificar_duplicatas.py`.

### Implementações:
1. **Dicionários de Catálogo ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionada `pomodoro` às `MARCAS_SUPERMERCADO`.
   * Adicionados `crocks`, `leve`, `pele`, `com pele`, `sem pele` e tamanhos de fralda em `TERMOS_VARIACAO_AGRUPADA`.

---

**Sessão 48 (Validação de Cortes de Carne PA, Formatos de Biscoito e Sêmola - Issue #44)**

**Data:** 04 de Agosto de 2026
**Objetivo:** Adicionar diferenciais de cortes de carne bovina (`p.a.`, `ponta de agulha`), formatos de biscoitos (`wafer` vs `rolo`/`recheado`), estampas de personagens (`minions`, `barbie`) e qualificador `sêmola` ao algoritmo de deduplicação.

### Implementações:
1. **Regras de Deduplicação ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Incorporada a palavra `sêmola` ao `STOPWORDS_QUALIFICADORES`.
   * Adicionados termos de personagens e formatos aos `TERMOS_VARIACAO_AGRUPADA` e `PROPRIEDADES_INCOMPATIVEIS`.
2. **Mesclagem no Firestore:**
   * Mesclado o Par #13 (`macarrao-espaguete-ricosa-pacote-400g-un` ➡️ `macarrao-de-semola-espaguete-ricosa-pacote-400g-un`), consolidando ofertas e criando sinônimo.

---

**Sessão 49 (Estados Físicos e Marcas de Ração no Algoritmo de Deduplicação - Issue #45)**

**Data:** 04 de Agosto de 2026
**Objetivo:** Adicionar incompatibilidade entre estados físicos de produtos (ex: Leite em pó vs Leite líquido/UHT) e adicionar marcas de ração animal (`Faro`, `Whiskas`, `Pedigree`, `Friskies`) para prevenção autônoma de falsos positivos no `identificar_duplicatas.py`.

### Implementações:
1. **Dicionários e Incompatibilidades ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionadas marcas de pet food (`faro`, `whiskas`, `pedigree`, `friskies`, `champ`) ao `MARCAS_SUPERMERCADO`.
   * Adicionada a regra `({"pó", "po"}, {"líquido", "liquido", "uht"})` às `PROPRIEDADES_INCOMPATIVEIS`.

---

**Sessão 50 (Incompatibilidade de Cortes Bovinos e Mesclagem de Flocão/Peixe - Issue #46)**

**Data:** 04 de Agosto de 2026
**Objetivo:** Adicionar matriz de incompatibilidade de cortes bovinos (`Coxão Mole`, `Músculo`, `Patinho`, `Alcatra`) e executar a mesclagem dos produtos do Flocão Dona Clara e Filé de Pescada Gó no Firestore.

### Implementações:
1. **Regras de Cortes Bovinos ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionadas combinações incompatíveis entre coxão mole, músculo, patinho e alcatra em `PROPRIEDADES_INCOMPATIVEIS`.
2. **Mesclagem no Firestore:**
   * Mesclado Par #24 (`farinha-de-milho-dona-clara-flocao-500g-un` ➡️ `flocao-de-milho-premium-dona-clara-pacote-500g-un`).
   * Mesclado Par #25 (`file-congelado-de-go-amazon-pacote-500g-un` ➡️ `file-de-pescada-go-congelada-amazon-norte-pacote-500g-un`).

---

**Sessão 51 (Adição de Marcas Excelência/Vittamax/Chanin e Mesclagem Leite Condensado Moça - Issue #47)**

**Data:** 04 de Agosto de 2026
**Objetivo:** Adicionar marcas de linguiças e alimentos de pet (`Excelência`, `Vittamax`, `Chanin`) ao dicionário de marcas conhecidas e executar a mesclagem das ofertas do Leite Condensado Nestlé para o produto canônico Leite Condensado Moça Nestlé.

### Implementações:
1. **Dicionário de Marcas ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionadas `excelência`, `excelencia`, `vittamax`, `chanin` ao `MARCAS_SUPERMERCADO`.
2. **Mesclagem no Firestore:**
   * Mesclado Par #28 (`leite-condensado-nestle-semidesnatado-caixa-395g-un` ➡️ `leite-condensado-semidesnatado-moca-nestle-tp-395g-un`).

---

**Sessão 52 (Regras de Faixa Etária Pet, Vendas a Granel e Mesclagem Ração Thor/Frango - Issue #48)**

**Data:** 04 de Agosto de 2026
**Objetivo:** Adicionar incompatibilidade entre faixas etárias de alimento pet (`Adultos` vs `Júnior/Filhote`), tratar qualificadores de venda a granel e executar mesclagens dos produtos da Ração Thor e Frango Americano.

### Implementações:
1. **Dicionários e Incompatibilidades ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionada a regra `({"adulto", "adultos"}, {"júnior", "junior", "filhote", "filhotes", "sênior", "senior"})` em `PROPRIEDADES_INCOMPATIVEIS`.
   * Adicionados `granel`, `a granel` ao `STOPWORDS_QUALIFICADORES`.
2. **Mesclagem no Firestore:**
   * Mesclado Par #32 (`racao-para-caes-thor-junior-a-granel-kg` ➡️ `racao-para-caes-thor-junior-quilo`).
   * Mesclado Par #34 (`americano-frango-congelado-kg` ➡️ `frango-americano-in-natura-congelado-kg`).

---

**Sessão 53 (Marca Triângulo Mineiro, Fígado/Miúdos e Mesclagem de Bisteca/Target - Issue #49)**

**Data:** 04 de Agosto de 2026
**Objetivo:** Incorporar a marca Triângulo Mineiro, matriz de incompatibilidade de miúdos/cortes (`fígado` vs `coxão duro`/`músculo`), linha `premium` vs `regular` e executar a mesclagem dos produtos de Bisteca do Peito e Carne em Conserva Target.

### Implementações:
1. **Dicionários e Incompatibilidades ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionada `triângulo mineiro` a `MARCAS_SUPERMERCADO`.
   * Adicionada a regra de incompatibilidade para `fígado` e linha `premium` em `PROPRIEDADES_INCOMPATIVEIS`.
2. **Mesclagem no Firestore:**
   * Mesclado Par #36 (`bisteca-do-peito-com-osso-resfriado-bovino-kg` ➡️ `bisteca-do-peito-dianteiro-bovino-resfriado-kg`).
   * Mesclado Par #38 (`carne-bovina-em-conserva-marca-target-lata-320g-un` ➡️ `carne-bovina-target-mista-lata-320g-un`).

---

**Sessão 54 (Regras de Pão Integral vs Tradicional, Acém vs Peito e Mesclagem Steak Rezende - Issue #50)**

**Data:** 04 de Agosto de 2026
**Objetivo:** Adicionar incompatibilidade entre receitas de pão (`Integral` vs `Tradicional/Branco`), acém com osso vs peito bovino com osso e executar a mesclagem das ofertas do Steak de Frango Rezende.

### Implementações:
1. **Dicionários e Incompatividades ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionada a regra `({"integral"}, {"tradicional", "comum", "branco"})` em `PROPRIEDADES_INCOMPATIVEIS`.
   * Adicionada a regra `({"acém", "acem"}, {"peito", "cupim"})` em `PROPRIEDADES_INCOMPATIVEIS`.
2. **Mesclagem no Firestore:**
   * Mesclado Par #43 (`steak-de-frango-empanado-rezende-embalagem-100g-un` ➡️ `steak-de-frango-rezende-congelado-100g-un`).

---

**Sessão 56 (Redirecionador Preventivo de Sinônimos no Ingest e Marca vs Genérico - Issue #52)**

**Data:** 05 de Agosto de 2026
**Objetivo:** Implementar o Redirecionador Preventivo por Sinônimos em cadeia no `functions/main.py` (`salvar_produto_e_oferta`) para evitar a criação de produtos duplicados no cadastro de ofertas e aprimorar as regras de Marca vs Genérico e cortes com osso no `identificar_duplicatas.py`.

### Implementações:
1. **Redirecionamento Preventivo em Cadeia ([functions/main.py](file:///Users/jplima/Documents/veja-o-preco-backend/functions/main.py)):**
   * Aprimorada a função `resolver_produto_id_com_sinonimo(db, produto_id)` com resolução em loop (até 5 saltos em cadeia) para redirecionar slugs antigos diretamente para o produto canônico correto antes do upsert no Firestore.
2. **Ajuste Fino de Marca vs Genérico ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionada a regra `bool(marcas_a) != bool(marcas_b)` no `eh_variacao_agrupada()` para auto-ignorar produtos de marca famosa comparados contra descrições genéricas sem marca.
   * Adicionada `copacol` às `MARCAS_SUPERMERCADO` e a regra `({"osso"}, {"filé", "file", "desossado"})` em `PROPRIEDADES_INCOMPATIVEIS`.

---

**Sessão 57 (Normalização Ortográfica de Contrafilé/Pá, Cortes Suínos/Arroz e Mesclagem Firestore - Issue #53)**

**Data:** 07 de Agosto de 2026
**Objetivo:** Adicionar mapeamentos de normalização ortográfica de OCR (`contra filé` ➡️ `contrafilé`, `pá` ➡️ `paleta`), incluir marca `Canção`, regras de cortes suínos, tipos de arroz e miúdos bovinos, e executar a mesclagem de 4 produtos duplicados no Firestore.

### Implementações:
1. **Inteligência & Normalização ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionadas marca `Canção` a `MARCAS_SUPERMERCADO`.
   * Adicionadas regras de incompatibilidade de cortes suínos (*paleta*, *panceta*, *costela*, *lombo*), tipos de arroz (*parboilizado* vs *branco/integral*) e miúdos (*mocotó* vs *fígado/língua/rabada/coração*) em `PROPRIEDADES_INCOMPATIVEIS`.
   * Adicionado `coração` aos `TERMOS_VARIACAO_AGRUPADA`.
2. **Mesclagens Executadas no Firestore:**
   * Mesclado Par #03 (`bisteca-do-contra-file-resfriado-bovino-kg` ➡️ `bisteca-do-contrafile-resfriada-bovina-kg`).
   * Mesclado Par #04 (`limpador-desengordurante-para-cozinha-veja-fragrancias-refil-400ml-un` ➡️ `limpador-desengordurante-veja-fragrancias-refil-400ml-un`).
   * Mesclado Par #06 (`pa-paleta-bovina-com-osso-resfriada-kg` ➡️ `paleta-com-osso-resfriada-bovina-kg`).
   * Mesclado Par #09 (`presunto-de-peru-rezende-delice-quilo-kg` ➡️ `rezende-presunto-de-peru-cozido-delice-pc-kg`).

---

**Sessão 55 (Marcas Baly/Dona Dê, Incompatibilidade de Peixes e Farinhas - Issue #51)**

**Data:** 04 de Agosto de 2026
**Objetivo:** Adicionar marcas de energético (`Baly`) e alimento (`Dona Dê`), implementar matriz de espécies de peixes incompatíveis (`Pescada` vs `Piramutaba`) e tipos de farinha (`Amarela` vs `Fina/Branca`) para conclusão da validação autônoma dos 53 potenciais duplicados.

### Implementações:
1. **Dicionários e Incompatibilidades ([identificar_duplicatas.py](file:///Users/jplima/Documents/veja-o-preco-backend/scripts/identificar_duplicatas.py)):**
   * Adicionadas `baly`, `dona dê` e `dona de` ao `MARCAS_SUPERMERCADO`.
   * Adicionadas matrizes incompatíveis para espécies de peixes (pescada, piramutaba, tambaqui, dourada, filhote, tucunaré, salmão, tilápia) e tipos de farinha em `PROPRIEDADES_INCOMPATIVEIS`.