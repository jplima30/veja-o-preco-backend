# Plano de Arquitetura: Firestore (Fase 4)

Este documento define a estrutura de dados, regras de negócio e fluxo de implementação para a persistência de dados no Cloud Firestore. É o blueprint da nossa próxima etapa de desenvolvimento.

---

## 🎯 Objetivo

Transformar as extrações pontuais (que hoje apenas retornam JSON) em um **banco de dados vivo e inteligente**, pronto para alimentar o App iOS com dados rápidos, atualizados e sem custo excessivo.

---

## 🏗️ Estrutura de Coleções (Modelagem)

A separação entre Produto e Oferta é a decisão mais importante dessa fase. Ela evita duplicatas e permite construir um **histórico de preços** ao longo do tempo.

### Coleção 1: `/produtos` (Catálogo Permanente)

```
/produtos/{produto_id}
    - nome:         "Arroz Agulhinha Tio Urbano"
    - marca:        "Tio Urbano"
    - unidade:      "5kg"
    - categoria:    "Mercearia"
    - imagem_url:   "https://..." (da API, Open Food Facts ou ícone)
    - criado_em:    Timestamp
    - atualizado_em: Timestamp
```

> **Regra de Ouro**: Um produto existe **uma única vez** nesta coleção.
> O `produto_id` é gerado a partir do nome normalizado: `arroz-tio-urbano-5kg`.

---

### Coleção 2: `/ofertas` (Registro Dinâmico)

```
/ofertas/{oferta_id}
    - produto_id:      "arroz-tio-urbano-5kg" (referência ao produto)
    - produto_nome:    "Arroz Agulhinha Tio Urbano" (desnormalizado para leitura rápida)
    - supermercado_id: "seja-economico-am" (referência ao supermercado)
    - loja:            "Seja Econômico"
    - preco:           20.25
    - preco_antigo:    24.90 (se disponível)
    - unidade:         "5kg"
    - categoria:       "Mercearia"
    - metodo:          "api_vipcommerce"
    - validade:        "2026-04-30" (ou null)
    - expira_em:       Timestamp (para o TTL automático)
    - criado_em:       Timestamp
```

> **Regra de Ouro**: Uma oferta tem uma **vida útil**. Após a validade, ela some da vitrine mas fica no histórico.
> **Otimização de Performance**: Utilizamos `WriteBatch` do Firestore para realizar até 500 gravações em uma única operação, reduzindo custos e tempo de resposta.

---

### Coleção 3: `/supermercados` (Cadastro de Lojas)

```
/supermercados/{supermercado_id}
    - nome:          "Seja Econômico"
    - rede:          "Grupo Econômico"
    - endereco:      "Augusto Montenegro, Belém-PA"
    - tipo_extracao: "api_json"
    - ativo:         true
    - criado_em:     Timestamp
```

> **Seed atual**: 8 supermercados cadastrados (Econômico, Atacadão, Guerreirão AM/BR, Mix Mateus, Assaí, Líder, Formosa).

---

## 🔄 Fluxo de Upsert (Lógica Central)

Este é o coração do sistema. Para cada produto extraído por qualquer scraper:

```
1. Normalizar o nome do produto
   Ex: "Arroz Tio Urbano 5kg" → "arroz-tio-urbano-5kg"

2. Verificar se o produto existe em /produtos/{produto_id}
   ├── NÃO EXISTE → Criar documento + buscar imagem (3 camadas)
   └── EXISTE     → Apenas atualizar "atualizado_em"

3. Criar novo documento em /ofertas com referência ao produto_id

4. Definir "expira_em":
   ├── Se a oferta tem validade → usar essa data
   └── Se não tem → agora + 7 dias (TTL padrão)
```

---

## 🖼️ Estratégia de Imagens (3 Camadas)

Para garantir que todo produto tenha uma imagem na vitrine:

| Prioridade | Fonte | Quando usar |
|:--- |:--- |:--- |
| 1️⃣ | **API da Loja** (VipCommerce/GraphQL) | Atacadão e Seja Econômico |
| 2️⃣ | **Open Food Facts API** | Líder, Formosa e qualquer produto sem imagem |
| 3️⃣ | **Ícone de Categoria** | Fallback final (Hortifruti, Carnes, etc.) |

> 🔗 Open Food Facts: `https://world.openfoodfacts.org/cgi/search.pl?search_terms={nome}&json=1`
> É gratuito, sem autenticação e possui milhares de produtos brasileiros.

---

## ⏰ Agendamento (Cloud Scheduler - CRON)

Duas Cloud Functions agendadas para manter o banco saudável:

| Job | Horário | O que faz |
|:--- |:--- |:--- |
| `atualizar_ofertas` | Todos os dias às 07:00 | Roda todos os scrapers e salva no Firestore |
| `limpar_ofertas_expiradas` | Todos os dias à meia-noite | Remove ofertas com `expira_em` no passado |

---

## 🔗 Endpoint Final para o App iOS

Após o Firestore estar populado, o App não precisará mais chamar os scrapers diretamente. Ele chamará apenas:

```
GET /get_ofertas_do_dia?categoria=Hortifruti&loja=Líder
```

Que retornará uma lista já formatada com produto + imagem + preço + validade, lida diretamente do Firestore (rápido, barato e offline-friendly).

---

## 📊 Projeção de Custo (Plano Blaze - Free Tier)

| Recurso Firebase | Limite Gratuito | Estimativa do Projeto |
|:--- |:--- |:--- |
| Firestore Leituras | 50.000/dia | ~5.000/dia ✅ |
| Firestore Escritas | 20.000/dia | ~200 escritas/dia ✅ |
| Cloud Functions | 125.000 invocações/mês | ~240/mês (8 scrapers x 30 dias) ✅ |
| Cloud Scheduler | 3 jobs gratuitos | 2 jobs usados ✅ |

> **Conclusão**: O projeto se mantém **100% dentro do tier gratuito** durante a fase inicial e tem espaço para escalar para dezenas de supermercados antes de gerar qualquer custo.


