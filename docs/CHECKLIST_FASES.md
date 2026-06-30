# Checklist de Implementação — Todas as Fases

> Fonte de verdade do progresso do projeto **Veja o Preço (Backend)**.
> Atualizado a cada conclusão importante.

---

## Fase 1 — Engenharia Reversa e Infraestrutura ✅

- [x] Criar projeto Firebase (`veja-o-preco`)
- [x] Configurar Cloud Functions em Python
- [x] Mapear API interna do Mateus (`api-proxy.php`)
- [x] Implementar `buscar_encarte_mateus` (catálogo de PDFs)
- [x] Validar bypass do Cloudflare via endpoint direto

---

## Fase 2 — Cérebro Gemini (Extração por IA) ✅

- [x] Integrar SDK `google-genai` (Gemini 3.1 Flash Lite)
- [x] Implementar `extrair_dados_encarte` (PDF → JSON)
- [x] Implementar `extrair_dados_imagem` (Vision AI para redes sociais)
- [x] Definir Contrato de Dados (produto, preco, unidade, categoria)
- [x] Resolver bloqueio de quotas (`429 RESOURCE_EXHAUSTED`)
- [x] Validar com encarte real do Mateus (Linguiça Seara R$18.99 ✅)

---

## Fase 3 — Scrapers de Extração Direta (Quick Wins) ✅

### Guerreirão (Augusto Montenegro)
- [x] Criar `buscar_encarte_guerreirao` (scraping HTML via BeautifulSoup)
- [x] Testar retorno JSON no emulador
- [x] Integrar salvamento no Firestore (`guerreirao-am`)

### Seja Econômico (VipCommerce)
- [x] Criar `buscar_encarte_economico` (API VipCommerce)
- [x] Mapear endpoint com Bearer JWT
- [x] Testar retorno JSON no emulador
- [x] Integrar salvamento no Firestore (`seja-economico-am`)

### Atacadão (Icoaraci)
- [x] Criar `buscar_encarte_atacadao` (API GraphQL)
- [x] Implementar regionalização (seller + regionId)
- [x] Testar retorno JSON no emulador
- [x] Integrar salvamento no Firestore (`atacadao-icoaraci`)

---

## Fase 4 — Persistência Firestore ✅

- [x] Definir arquitetura de coleções (`produtos`, `ofertas`, `supermercados`)
- [x] Implementar módulo Firestore (`normalizar_nome`, `buscar_imagem`, `salvar_produto_e_oferta`)
- [x] Executar seed de supermercados (8 lojas)
- [x] Validar integração ponta-a-ponta: API → Firestore real (Coca Cola R$4.32 ✅)
- [x] Remover função duplicada `buscar_encarte_economico`

---

## Fase 5 — Integração Completa (Scrapers IA + Firestore) ✅

### Endpoint para o App iOS
- [x] Criar `GET /get_ofertas_do_dia` (leitura do Firestore → JSON para SwiftUI) ✅ **Validado na nuvem** (25/04/2026)

### Scrapers IA → Firestore (Redes Maiores)
- [x] Integrar `buscar_encarte_mateus` com `salvar_produto_e_oferta` (Gemini PDF → Firestore)
- [x] Construir motor de navegação para Instagram (`cron_playwright.py` + perfil persistente natural sem stealth)
- [x] Integrar `extrair_dados_imagem` (Líder) com Firestore (`lider-am`)
- [x] Integrar `extrair_dados_imagem` (Formosa) com Firestore (`formosa-am`)
- [x] Integrar `extrair_dados_imagem` (Guerreirão BR) com Firestore (`guerreirao-br`)
- [x] Integrar `extrair_dados_imagem` (Assaí) via Playwright (`assai-am`)
- [x] Validar saída do Gemini compatível com `salvar_produto_e_oferta` (Uso do modelo Gemini 3.1 Flash Image para visão computacional) ✅ **Backend Estabilizado** (28/04/2026)

### Auditoria e Logs
- [x] Estruturar pastas locais de `auditoria_visual/` (organizadas por YYYY-MM-DD_Dia)
- [x] Salvar frames e imagens originais extraídas pelo Playwright nas pastas de auditoria
- [x] Forçar o VS Code a ler o `venv` Python local para evitar erros falsos de importação (`pyrightconfig.json` e `.vscode/settings.json`)

### Automação CRON e Refino Local
- [x] Implementar `cron_playwright.py` como motor local de disparo para o Instagram
- [x] Criar `captura_visivel.command` para monitoramento em tempo real no macOS
- [x] Implementar divisão de arquivos por janelas de horário (`10h` e `14h`)
- [x] Configurar Triagem Local Consciente (OCR focado na janela atual)
- [x] Criar Cloud Function `atualizar_ofertas` (Scheduler diário — roda APIs e PDFs)
- [x] Criar Cloud Function `limpar_ofertas_expiradas` (Scheduler noturno, TTL 7 dias)

### Deploy e Validação
- [x] `firebase deploy --only functions` ✅ **8 funções publicadas** (26/04/2026)
- [x] Validar funções na nuvem (URLs públicas)
- [x] Refinar Prompt de IA para lidar com cenários híbridos de vídeo (ignorar bebidas sem perder alimentos)
- [x] Redeploy após integração dos scrapers IA


### Blindagem e Otimização (Sessão 16)
- [x] Consolidar modelos Gemini 3.1 (Image para Visão, Lite para PDFs)
- [x] Implementar Whitelist de Categorias (Alimentos, Higiene e Limpeza)
- [x] Adicionar filtro de descarte no backend para categorias proibidas (Bazar/Eletrônicos/Álcool)
- [x] Implementar limpeza automática semanal da pasta de auditoria visual
- [x] Reorganizar manual de operação local (`readme-validators.md`)

---

## Fase 5.1 — CRON Inteligente e Caching no Storage (Issue #4) ✅

- [x] Adicionar dependência `Pillow==10.3.0` no `functions/requirements.txt`
- [x] Implementar a função `baixar_e_otimizar_imagem(url, produto_id)` em `main.py`
- [x] Validar localmente a otimização de imagem na pasta `auditoria_visual/imagens_otimizadas/`
- [x] Configurar upload de imagem para o Firebase Storage
- [x] Integrar bypass (radar de repetição) no script `salvar_produto_e_oferta` para reaproveitar imagens
- [x] Denormalizar a URL da imagem nas ofertas no Firestore e ajustar endpoint `/get_ofertas_do_dia`

---

## Manutenção — Junho 2026 (Sessão 21) ✅

### Correção de Timeout no Scanner do Instagram
- [x] Diagnosticar falhas de timeout nos screenshots de Reels do Instagram no cron das 10h
- [x] Configurar a variável de ambiente `PW_TEST_SCREENSHOT_NO_FONTS_READY=1` em `cron_playwright.py` para ignorar espera de fontes
- [x] Otimizar captura de tela de vídeos utilizando `locator.screenshot()` diretamente no elemento
- [x] Incrementar o timeout padrão de screenshots para 15000ms
- [x] Validar o funcionamento de ponta a ponta com execução manual (`--force`)



## Fase 6 — App iOS (SwiftUI) ⚙️

- [x] Conectar App ao Firestore (Coleção `ofertas`)
- [x] Implementar tela de ofertas com dados reais (Mapeamento de chaves via CodingKeys e AsyncImagePhase)
- [ ] Timeline de preços
- [ ] Alertas de hortifruti

---

## Fase 7 — Premium e Analytics 🔒 *(futura)*

- [ ] Endpoint `GET /historico_precos` (média por loja nos últimos N meses)
- [ ] Rotação inteligente de modelos Gemini (fallback entre modelos)
- [ ] Escala para outros bairros (novas unidades das mesmas redes)

---

*Última atualização: 30/04/2026 — Backend blindado com Whitelist e Modelos Gemini 3.1 (Fase 5+ Concluída)*
