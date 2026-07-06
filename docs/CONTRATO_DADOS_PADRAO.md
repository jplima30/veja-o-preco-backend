# Contrato de Dados Unificado - Veja o Preço

Este documento define o padrão obrigatório de resposta para **todas** as Cloud Functions do backend (Scrapers Diretos e Extração via I.A.). Isso garante que o App iOS receba dados consistentes independente da origem.

## Estrutura de Resposta (JSON)

Toda função de busca de encarte deve retornar um objeto JSON com a seguinte estrutura:

### 1. Cabeçalho (Metadata)
| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `sucesso` | Boolean | `true` se a extração funcionou. |
| `loja` | String | Nome do supermercado (Ex: "Atacadão", "Mix Mateus"). |
| `metodo` | String | Origem do dado (Ex: "API Direta", "Gemini 3.1 Flash Lite"). |
| `quantidade` | Integer | Total de itens retornados. |
| `uso_tokens` | Object | (Opcional) Telemetria de custo para I.A. (campos: `total`, `prompt`, `resposta`). |

### 2. Lista de Itens (`itens`)
| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `produto` | String | Nome completo + marca (Ex: "Arroz Agulhinha Tio Urbano"). |
| `preco` | Number | Preço de venda em formato numérico (Ex: 24.90). |
| `unidade` | String | Unidade de medida (Ex: "kg", "un", "500g", "l"). |
| `categoria` | String | Um dos 8 grupos padronizados: `ALIMENTOS`, `CARNES`, `HORTIFRUTI`, `PADARIA`, `BEBIDAS`, `HIGIENE`, `LIMPEZA`, `FRIOS_LATICINIOS`. |
| `imagem` | String | URL completa da imagem do produto. |
| `validade` | String | Data até quando a oferta é válida. |

---

## Exemplo de Resposta com I.A. (Vision/PDF)

```json
{
  "sucesso": true,
  "loja": "Mix Mateus",
  "metodo": "Gemini 3.1 Flash Lite (PDF)",
  "quantidade": 1,
  "uso_tokens": { "total": 1250, "prompt": 1000, "resposta": 250 },
  "itens": [
    {
      "produto": "Arroz Fazenda 5kg",
      "preco": 20.25,
      "unidade": "un",
      "categoria": "Mercearia",
      "validade": "Válido até 22/04/2026"
    }
  ]
}
```

#### Exemplo 2: Visão Computacional (Instagram/Assaí)
```json
{
  "sucesso": true,
  "loja": "Assaí Atacadista",
  "metodo": "Gemini 3.1 Flash Image (Vision)",
  "quantidade": 1,
  "uso_tokens": { "total": 2100, "prompt": 1800, "resposta": 300 },
  "itens": [
    {
      "produto": "Leite Ninho 400g",
      "preco": 15.90,
      "unidade": "un",
      "categoria": "Mercearia",
      "validade": "Oferta de hoje"
    }
  ]
}
```
```

## Regras de Ouro para Implementação
1. **Sem placeholders**: Se a imagem não existir, retorne string vazia `""`.
2. **Nomes Limpos**: Remova excesso de espaços ou caracteres especiais dos nomes.
3. **Preços Reais**: Nunca retorne o preço como String (ex: "R$ 10"). Deve ser sempre `Number`.
4. **Categorização**: Se a API original não der a categoria, o robô deve tentar inferir ou usar "Geral".
5. **Telemetria**: Sempre inclua `uso_tokens` em funções que utilizam modelos Generativos.
6. **Estratégia de Modelos**: 
   - **Gemini 3.1 Flash Image**: Usado para Vision (fotos/vídeos) onde o Q.I. visual é crítico (Ex: Instagram/Assaí).
   - **Gemini 3.1 Flash Lite**: Usado para PDFs e tarefas de alto volume para otimização de custo (Ex: Mix Mateus).
7. **Filtro de Conteúdo (Global)**: O backend deve extrair APENAS produtos alimentícios. Bebidas alcoólicas, bazar e eletrônicos devem ser filtrados na fonte pela I.A.
