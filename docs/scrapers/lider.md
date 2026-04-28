# Análise Técnica: Grupo Líder

O Líder é extraído via **Visão Computacional**, pois não possui um e-commerce estruturado com preços para as unidades locais em tempo real, priorizando divulgações em redes sociais.

## 👁️ Estratégia de Extração (Vision)
**Método**: `extrair_dados_imagem` (Gemini 3.1 Flash Lite)

### Informações Técnicas
- **Fontes**: 
  - [Instagram @supermercadoslider](https://www.instagram.com/supermercadoslider/)
  - [Facebook Grupo Líder](https://www.facebook.com/lidersupermercado)
- **Filtro**: Apenas Alimentos (Food Only).
- **Dificuldade**: 🔴 Alta (Devido ao formato de Reels e Carrosséis).

### Fluxo de Trabalho
1. Captura-se a URL da imagem da oferta (ou frame do vídeo).
2. O link é enviado via **POST** para o backend.
3. A I.A. filtra itens de bazar/bebidas alcoólicas e retorna apenas alimentos.

### Exemplo de Sucesso (Validado)
- **Produto**: Pizza Líder Semipronta
- **Preço**: R$ 49,90/kg
- **Tokens**: ~1400 por chamada.
