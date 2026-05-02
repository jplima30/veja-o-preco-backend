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
1. **Migração para Gemini 3.1 Flash Lite:** Adotamos o modelo mais recente (`gemini-3.1-flash-lite-preview`) por ser otimizado para extrações rápidas e de baixo custo, mantendo alta precisão.
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
2. **Motor Playwright (`cron_playwright.py`):** Sistema reescrito para navegação local em redes sociais, capaz de "roubar" URLs da aba de network (sniffer) e fatiar vídeos do Reels em frames (imagens múltiplas) baseados no tamanho do vídeo.
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
1. **Modelos de Elite (Gemini 3.1):** Consolidamos o uso do `gemini-3.1-flash-image-preview` para visão (fotos/vídeos) e `gemini-3.1-flash-lite-preview` para textos (PDFs), garantindo o melhor equilíbrio entre inteligência visual e custo.
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
2. **Modelo Gemini 3.1 Confirmado**: Reafirmamos o uso dos modelos `gemini-3.1-flash-image-preview` e `gemini-3.1-flash-lite-preview` como os motores oficiais de extração na nuvem.
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

*Última atualização: 02/05/2026 — Sessão 18: Blindagem de Dados e Otimização Firestore.*