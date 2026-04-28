# Análise Técnica: Mix Mateus (Jaderlândia)

Este documento registra a inteligência de extração híbrida desenvolvida para o Grupo Mateus, utilizando rastreamento de API e Inteligência Artificial.

## Informações Gerais
- **URL Alvo**: `https://ofertasmateus.com/pa/ananindeua/mateus-jaderlandia`
- **Método**: Híbrido (API de Catálogo + Gemini 3.1 Flash Lite)
- **Tipo de Dados**: PDFs (Encartes Semanais)

## Estratégia de Extração (2 Fases)

### Fase 1: O Localizador (`buscar_encarte_mateus`)
O site do Mateus utiliza um proxy para servir os encartes.
- **API Endpoint**: `https://ofertasmateus.com/api-proxy.php?endpoint=/encartes/pa/ananindeua/mateus-jaderlandia?marca=SM`
- **Função**: Captura o `download_link` do PDF mais recente.

### Fase 2: O Cérebro (`extrair_dados_encarte`)
Como os dados estão "presos" no formato visual do PDF, utilizamos o **Gemini 3.1 Flash Lite**.
- **Modelo**: `gemini-3.1-flash-lite-preview`
- **Processo**:
    1. Download do PDF para diretório temporário.
    2. Upload para a Google Files API.
    3. Processamento via Prompt estruturado (JSON Output).
    4. Mapeamento para o **Contrato de Dados Padrão**.

## Amostra de Resposta da I.A. (JSON Bruto)
```json
{
  "itens": [
    {
      "produto": "Arroz Tio Urbano 5kg",
      "preco": 24.90,
      "unidade": "un",
      "categoria": "Mercearia",
      "imagem": "",
      "validade": "Válido até 22/04/2026"
    }
  ]
}
```

## Manutenção
- Se a API do Mateus parar de retornar PDFs, verificar se a estrutura do `api-proxy.php` mudou (inspecionar Network Tab do site).
- Se a I.A. começar a falhar, verificar o `response_schema` ou o `prompt_instrucao` no `main.py`.
