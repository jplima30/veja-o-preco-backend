# Estado atual do ecossistema — 01/10/2026

Referências: backend #77 e app #16. Este levantamento distingue comportamento implementado de objetivos e registros históricos.

## Integração e infraestrutura

O app SwiftUI consulta diretamente `ofertas` no projeto Firebase `veja-o-preco`, via FirebaseFirestore. `get_ofertas_do_dia` existe, mas não monta a vitrine atual. O bundle iOS é `com.joaosilva.VejaOpreco`.

Há 11 Cloud Functions de segunda geração, Python 3.12, em `us-central1`. O código usa Vertex AI (`gemini-3.1-flash-lite`). Firestore Native Standard contém `ofertas`, `produtos`, `supermercados`, `historico_precos`, `sinonimos` e `duplicatas_ignoradas`. A leitura de clientes é pública apenas para `ofertas` e `produtos`; escritas de clientes são negadas. Imagens são publicadas pelo Admin SDK no Storage.

A atualização agendada no código ocorre às 10h e 14h (America/Belem); a limpeza de ofertas expiradas, às 23h. A captura de Instagram e parte dos encartes usa Playwright local, seguida de OCR, envio para extração, auditoria de categorias, deduplicação e curadoria.

## Contrato consumido pelo app

`produto_nome`, `preco`, `unidade` e `categoria` alimentam o card. Campos opcionais incluem `produto_id`, `imagem_url`, `loja`, `supermercado_id`, `validade` e `expira_em` (Timestamp → Date). O ID vem de `@DocumentID`.

A consulta exige `expira_em >= agora` no servidor e aplica `estaValida` novamente no cliente. Documentos sem `expira_em` não entram nessa consulta, embora o modelo isoladamente considere nil válido. `validade` é texto de apresentação, sem interpretação de data pelo app.

Há nove categorias principais e `OUTROS`; categorias desconhecidas são decodificadas como `ALIMENTOS`. Documentos que falham no decode são descartados por `try?`/`compactMap`. A consulta é pontual, sem listener em tempo real.

## Persistência e imagens

O helper central normaliza nomes/unidades, resolve sinônimos, registra histórico diário e evita ofertas repetidas. Preço novo expira ofertas anteriores do mesmo produto e loja. Ofertas de lojas irmãs podem compartilhar um documento com `supermercado_ids`; `supermercado_id` permanece como loja principal.

A extração PDF tem gravação própria em batch e não usa o helper central. Portanto, normalização, campos e histórico não são equivalentes em todos os caminhos.

A ingestão automática usa imagens 200×200. A curadoria posterior usa 400×400, normalmente com fundo branco e cache-buster. Resolução, correspondência com marca/variante e margem de 20px não são garantidas para todo o catálogo. As ondas anteriores são entregas históricas, não uma certificação permanente da vitrine.

## Pendências conhecidas

- A expiração atual é sete dias após captura/renovação, mesmo quando há validade textual. Não há conversão dessa validade em expiração no helper examinado.
- O app ainda não usa `supermercado_ids` no filtro; ofertas compartilhadas podem faltar na loja secundária.
- O fluxo PDF não registra o mesmo histórico diário do helper central.
- Fusões de produtos não remapeiam automaticamente o histórico de preços.
- Existem IDs legados de lojas e diferenças entre cadastro e ofertas; o app deriva o carrossel das ofertas.
- O app ainda não apresenta histórico de preços nem notificações. Erros de carregamento ficam no console; o gesto de atualização não aguarda a Task interna.
- Curadoria contínua e revisão dos cards permanecem nas issues #11, #12 e #13 do app. Esta sincronização não encerra essas tarefas.

## Operação e validação desta integração

O diretório `functions/venv` atende Firebase/IA; `venv_triagem` atende Playwright/OCR. Logs atuais são `scripts/cron_hoje.log` e `cron_AAAA-MM-DD_10h|14h.log`, com poda de logs de janela antigos.

Scripts de seed, integração, curadoria, fusão e limpeza podem alterar produção. Iniciar apenas o emulador de Functions não garante Firestore emulado: conferir `FIRESTORE_EMULATOR_HOST` e o destino do Admin SDK antes de executar. `seed_firestore.py` apaga coleções; não é uma consulta.

Validação realizada: `py_compile` de `functions/main.py`, build iOS Simulator com `CODE_SIGNING_ALLOWED=NO` e revisão do diff. Não houve teste funcional no simulador, execução de crawlers, alterações de dados nem deploy. A versão do código implantado nas Functions não foi confrontada com a fonte local.

A sincronização integra registros das sessões 86–102 do backend e o filtro de expiradas do app; atualiza os Markdown e as duas Wikis, com commits rastreáveis, merge `--no-ff` e retorno a `develop`.


---

## Curadoria aplicada — 02/10/2026 (#78)

109 produtos e 115 ofertas ativas receberam as fotos selecionadas pelo usuário no preview. A opção Coxão Mole / Chã de Dentro Bovino Resfriado permaneceu desmarcada e não foi alterada. A seleção exportada foi confrontada com os 109 checkboxes marcados.

As imagens foram publicadas em `produtos/{produto_id}.jpg`, JPEG RGB de 400 × 400, proporção preservada e transparências compostas sobre branco. O cadastro mestre recebeu `imagem_origem=curadoria_manual` e `atualizado_em`; as ofertas vinculadas receberam a mesma URL com `?t=<timestamp>`. No app, `OfertaDetalheView` reconhece `?t=` e mostra o selo verde e o texto “400 × 400 px (Curadoria HD)”. O selo pertence à interface e não foi desenhado nas fotos.

Verificação posterior: 109 URLs públicas responderam com bytes iguais aos arquivos preparados, JPEG 400 × 400; os 109 produtos e 115 ofertas foram relidos e conferidos. Não houve alteração de preços, validade, código Swift ou Functions, nem deploy. A exibição do selo foi conferida pela condição implementada no código, sem teste funcional no simulador. O app usa consulta pontual; é necessário atualizar a vitrine para receber as novas URLs.

65 fotos selecionadas tinham ressalvas de variante/tamanho ou representação genérica no preview. A aprovação permite aplicar essas escolhas, mas não comprova correspondência exata de todos os rótulos. As observações e fontes foram preservadas no relatório individual. Das 202 entradas sinalizadas na auditoria, 93 ficaram fora deste lote (92 sem candidata confiável e uma candidata desmarcada).

Antes da gravação foram preservados os documentos Firestore com tipos originais, JSON legível, arquivos anteriores do Storage, gerações e seleção aprovada. Uma tentativa inicial recebeu HTTP 403, restaurou o arquivo original e não alterou Firestore; a aplicação concluída incluiu a publicação pública utilizada pelo fluxo existente. A atualização dos 224 documentos ocorreu em batch com pré-condições de versão.

Rastreabilidade: [issue backend #78](https://github.com/jplima30/veja-o-preco-backend/issues/78); relatório `docs/CURADORIA_2026-10-02.md`. Backup local e evidências: `curadoria-2026-10-02/aplicacao` no diretório de visualizações da sessão Codex; não versionar o backup binário.
