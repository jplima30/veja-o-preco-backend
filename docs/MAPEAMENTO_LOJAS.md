# 🗺️ Mapeamento de Supermercados (Belém/Ananindeua)

Este documento centraliza a inteligência de onde buscar os dados e qual o nível de esforço para cada loja no arco da Augusto Montenegro e BR-316.

---

## 📍 Localização Estratégica: Arco Augusto Montenegro - BR-316

| Status | Supermercado | Rede | Dificuldade | Método de Extração |
| :---: | :--- | :--- | :--- | :--- |
| ✅ | [Seja Econômico (AM)](https://www.grupoeconomico.com.br/) | Econômico | 🟢 **Baixíssima** | **API VipCommerce** (Bearer Token) |
| ✅ | [Atacadão Ananindeua](https://www.atacadao.com.br/catalogo) | Atacadão | 🟢 **Baixíssima** | **API GraphQL** (Regionalizada) |
| ✅ | [Meio a Meio Guerreirão (AM)](https://portal.qrofertas.com/meio-a-meio-o-guerreiro/) | Guerreirão | 🟢 **Baixíssima** | **HTML/BeautifulSoup** (Microdata) |
| ✅ | [Mix Mateus Jaderlândia](https://ofertasmateus.com/pa/ananindeua/mateus-jaderlandia) | Grupo Mateus | 🟡 **Média** | **API + Gemini 3.1 Flash Lite** (PDF) |
| ✅ | [Meio a Meio Guerreirão (BR)](https://www.instagram.com/mmguerreirao/) | Guerreirão | 🔴 **Alta** | **Gemini 3.1 Flash Image** (Vision/Instagram) |
| ✅ | [Assaí Atacadista](https://www.assai.com.br/ofertas/para/assai-augusto-montenegro) / [Instagram](https://www.instagram.com/assaiatacadistaoficial/) | Assaí | 🟢 **Baixa** | **Híbrido (Playwright Site + Radar Instagram)** |
| ✅ | [Líder Augusto Montenegro](https://www.instagram.com/supermercadoslider/) / [Facebook](https://www.facebook.com/lidersupermercado) | Grupo Líder | 🔴 **Alta** | **Vision AI (OCR Fotos/Vídeos)** |
| ✅ | [Formosa Augusto Montenegro](https://www.facebook.com/formosaoficial) | Formosa | 🔴 **Alta** | **Vision AI + Filtro "Super"** |

---

## 📝 Parecer Técnico de Extração (Scraping)

### 1. Política Global de Categorias (Novo!) ✅
- **Regra**: Apenas **ALIMENTOS**.
- **Exclusão**: Bebidas alcoólicas, Bazar, Higiene (exceto se essencial), Eletrônicos.
- **Implementação**: O prompt da I.A. foi treinado para filtrar automaticamente esses itens na fonte.

### 2. Supermercados Líder (Castanheira/AM)
- **Método**: Híbrido Redes Sociais.
- **Fontes**: Instagram Reels e Posts no Facebook.
- **Funcionamento**: A função `extrair_dados_imagem` processa o frame das ofertas. A I.A. ignora postagens institucionais ou vídeos sem preços.

### 3. Meio a Meio Guerreirão (BR) - CONCLUÍDO ✅
- **Método**: Visão Computacional.
- **Funcionamento**: Extração via Instagram bem-sucedida.

### 4. Assaí Atacadista (Unidade Augusto Montenegro) - CONCLUÍDO ✅
- **Método**: Navegação Local com Playwright + Vision AI.
- **Funcionamento**: O script local detecta todas as abas e clusters de encartes, baixa as imagens via IP residencial (evitando bloqueios de CDN) e envia para a Vision API.
