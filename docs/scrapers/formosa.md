# Análise Técnica: Grupo Formosa

O Formosa exige uma filtragem inteligente, pois a marca "Formosa" engloba o Supermercado e o Bazar (Mix).

## 👁️ Estratégia de Extração (Vision)
**Método**: `extrair_dados_imagem` (Gemini 3.1 Flash Lite)

### Informações Técnicas
- **Fontes**: 
  - [Facebook Formosa Oficial](https://www.facebook.com/formosaoficial)
- **Filtro Especial**: A I.A. deve distinguir ofertas do "Super Formosa" (Alimentos) e ignorar o "Formosa Mix" (Eletro/Bazar).
- **Dificuldade**: 🔴 Alta.

### Fluxo de Trabalho
Utiliza o motor de visão para ler encartes complexos e extrair dados estruturados, incluindo a validade das ofertas.

### Exemplo de Sucesso (Validado)
- **Produto**: Banana Prata
- **Preço**: R$ 8,35/kg
- **Validade**: Extraída automaticamente do rodapé/imagem.
- **Tokens**: ~1450 por chamada.
