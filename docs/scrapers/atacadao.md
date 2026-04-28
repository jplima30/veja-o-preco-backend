# Análise Técnica: Atacadão (Catálogo Digital)

Este documento registra a inteligência de extração para o catálogo nacional do Atacadão, focando na regionalização de Belém/Icoaraci.

## Informações Gerais
- **URL Alvo**: `https://www.atacadao.com.br/api/graphql`
- **Tipo de API**: GraphQL (via GET para cache)
- **Regionalização**: Essencial. Sem regionalização, a API retorna erro 500 ou preços vazios.

## Estratégia de Regionalização
O Atacadão exige dois campos cruzados:
1.  **seller_id**: Identifica a loja física. (Ex: `atacadaobr153` para Belém).
2.  **region_id**: É o Base64 da string `SW#<seller_id>`.

## Estrutura do JSON Original (Bruto - GraphQL)
Exemplo simplificado de como o Atacadão retorna cada item:

```json
{
  "data": {
    "productSearch": {
      "products": [
        {
          "productName": "Arroz Agulhinha Tipo 1 5kg Tio Urbano",
          "brand": "Tio Urbano",
          "items": [
            {
              "images": [{ "imageUrl": "https://img.atacadao.com.br/..." }],
              "sellers": [
                {
                  "commertialOffer": {
                    "Price": 24.90,
                    "ListPrice": 26.90,
                    "AvailableQuantity": 500
                  }
                }
              ]
            }
          ]
        }
      ]
    }
  }
}
```

## Query Crítica (ProductsQuery)
A busca é feita enviando um JSON stringificado no parâmetro `variables`.
- **productClusterIds**: O valor `312` geralmente aponta para o "Catálogo de Ofertas" do site.

## Desafios Superados
- **Erro 500**: Resolvido ao migrar de POST para GET e incluir o `region-id` nos `selectedFacets`.
- **Bloqueio de Terminal**: O terminal local pode ter problemas de DNS, mas o Python no venv/Firebase resolve corretamente.
