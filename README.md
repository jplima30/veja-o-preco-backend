# 🛒 Veja o Preço - Backend (v2)

Backend robusto desenvolvido em **Firebase Cloud Functions (Python)** para centralizar ofertas de supermercados de Belém e Ananindeua. 

O projeto utiliza uma arquitetura híbrida de extração de dados, combinando rastreamento de APIs tradicionais com **Inteligência Artificial Generativa (Vision & PDF)** e automação via **Playwright**.

---

## 🚀 Tecnologias e Inovações
- **Core**: Python 3.12 + Firebase Functions.
- **I.A. Engine**: **Gemini 3.1** (Flash Image para Visão e Flash Lite para PDFs).
- **Automation**: **Playwright Stealth** para captura de redes sociais.
- **Computer Vision**: **EasyOCR** local para triagem inteligente de imagens.
- **Database**: **Cloud Firestore** com arquitetura de deduplicação e histórico.

> [!TIP]
> Confira os detalhes técnicos completos na nossa **[página de Arquitetura](https://github.com/jplima30/veja-o-preco-backend/wiki/Arquitetura)**.

---

## 🏗️ Fluxo de Funcionamento
1. **Captura**: Robôs locais monitoram redes sociais e APIs.
2. **Triagem**: O sistema filtra apenas imagens que contêm ofertas reais, economizando custos de API.
3. **Extração**: O Gemini processa as evidências e extrai dados estruturados (JSON).
4. **Persistência**: Dados são normalizados e salvos no Firestore seguindo um **[Contrato de Dados](https://github.com/jplima30/veja-o-preco-backend/wiki/Contrato-de-Dados)** rígido.

---

## ✅ Supermercados Integrados
- [x] **Mix Mateus**: API + Gemini (PDF).
- [x] **Atacadão**: API GraphQL (Regionalizado).
- [x] **Seja Econômico**: API Direta.
- [x] **Guerreirão (AM/BR)**: Scraping + Vision AI.
- [x] **Assaí Atacadista**: Playwright + Vision AI.
- [x] **Líder & Formosa**: Extração via I.A. Multimodal.

---

## 🛠️ Operação e Testes
Para rodar os robôs ou validar os scrapers manualmente, consulte o nosso **[Guia de Operação Local](https://github.com/jplima30/veja-o-preco-backend/wiki/Operacao-Local)**.

Exemplo de validação rápida:
```bash
python3 scripts/ver_ofertas_banco.py
```

---

## 📚 Documentação Completa (Wiki)
Para uma visão detalhada de cada fase do projeto, acesse a nossa **Wiki oficial**:
- **[🏠 Home](https://github.com/jplima30/veja-o-preco-backend/wiki)**
- **[✅ Checklist de Fases](https://github.com/jplima30/veja-o-preco-backend/wiki/Checklist-de-Implementacao)**
- **[🛒 Supermercados](https://github.com/jplima30/veja-o-preco-backend/wiki/Supermercados)**

---
**Desenvolvido com Antigravity (Google DeepMind)** 🦾🤖
