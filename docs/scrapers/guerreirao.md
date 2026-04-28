# Análise Técnica: Meio a Meio Guerreirão

O Guerreirão possui duas estratégias distintas de extração dependendo da unidade, devido à forma como as ofertas são publicadas.

---

## 🏗️ Unidade 1: Augusto Montenegro (AM)
**Método**: Extração Direta via HTML (Scraping Tradicional)

### Informações Técnicas
- **URL**: `https://portal.qrofertas.com/meio-a-meio-o-guerreiro/`
- **Tecnologia**: BeautifulSoup4 (Python)
- **Saúde**: Estável. Utiliza Microdata (SEO) para capturar preços formatados para máquinas.

### Seletores CSS
1. **Container**: `.boxProdutoEst`
2. **Nome**: `span[itemprop="name"]`
3. **Preço**: `span[itemprop="price"]` (Atributo `content`).

---

## 👁️ Unidade 2: BR-316 (BR)
**Método**: Visão Computacional (Gemini 3.1 Flash Lite Vision)

### Informações Técnicas
- **Fonte**: [Instagram @mmguerreirao](https://www.instagram.com/mmguerreirao/)
- **Tecnologia**: `google-genai` + Gemini 3.1 Flash Lite.
- **Saúde**: Depende da qualidade das fotos postadas. Requer envio de URL da imagem via método **POST**.

### Fluxo de Funcionamento
Como não há um site de e-commerce para esta unidade, capturamos o link direto da imagem (`.jpg`) do Instagram e o enviamos para a função `extrair_dados_imagem`.

**Exemplo de Chamada (cURL):**
```bash
curl -X POST https://SUA_URL_FIREBASE/extrair_dados_imagem \
-H "Content-Type: application/json" \
-d '{"url": "LINK_DA_FOTO_INSTAGRAM"}'
```

### Amostra de Extração (Vision)
```json
{
  "loja": "Extração via Visão (IA)",
  "metodo": "Gemini 3.1 Flash Lite (Vision)",
  "itens": [
    {
      "produto": "Brocolis",
      "preco": 32.29,
      "unidade": "Kg",
      "categoria": "Hortifruti"
    }
  ]
}
```

---

## ⚠️ Desafios e Manutenção
1. **Unidade AM**: Se os preços pararem de aparecer, verifique se a classe `.boxProdutoEst` foi renomeada no portal QROfertas.
2. **Unidade BR**: Links do Instagram expiram rápido. A captura da imagem e o envio para a I.A. devem ser feitos em uma janela curta de tempo ou o App deve revalidar o link.
3. **Headers**: Ambas as unidades exigem `User-Agent` de navegador real para evitar erro **403 Forbidden**.
