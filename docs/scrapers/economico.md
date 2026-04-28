# Análise Técnica: Seja Econômico (VipCommerce)

Este documento registra a inteligência de extração para o Seja Econômico (Grupo Econômico), que utiliza a plataforma VipCommerce.

## Informações Gerais
- **URL Alvo**: `https://services.vipcommerce.com.br/api-admin/v1/...`
- **Plataforma**: VipCommerce
- **Método**: API JSON estruturada.

## Segurança e Cabeçalhos
A API é protegida contra acessos externos simples (Erro 403). Para funcionar, os seguintes headers são obrigatórios:
1.  **DomainKey**: `grupoeconomico.com.br`
2.  **OrganizationId**: `315`
3.  **Authorization**: Token Bearer (JWT) gerado no login/abertura do site.

## Mapeamento de Dados
- **Nome**: Campo `descricao`.
- **Preço**: Priorizar `preco_promocional` se disponível, caso contrário `preco_venda`.
- **Imagens**: CDN fixo no padrão `https://static.vipcommerce.com.br/img/produtos/{org_id}/v/{filename}`.

## Estrutura do JSON Original (Bruto - VipCommerce)
Para referência, veja como os dados chegam da API antes da nossa tradução:

```json
{
  "status": true,
  "data": [
    {
      "id_produto": "12345",
      "descricao": "ARROZ BRILHANTE PARB 5KG",
      "preco_venda": "21.50",
      "preco_promocional": "18.70",
      "unidade": "UN",
      "imagem_principal": "nome_da_imagem.jpg",
      "estoque": 100
    }
  ],
  "total": 189
}
```

## Manutenção
Caso o scraper retorne `403 Forbidden`, o token JWT no `main.py` expirou. É necessário abrir o site, capturar o novo header `Authorization` via Network Tab e atualizar a função.
