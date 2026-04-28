# 🛒 Veja o Preço - Backend (v2)

Backend robusto desenvolvido em **Firebase Cloud Functions (Python)** para centralizar ofertas de supermercados de Belém e Ananindeua. 

Este projeto utiliza uma arquitetura híbrida de extração de dados, combinando rastreamento de APIs tradicionais com **Inteligência Artificial Generativa (Vision & PDF)**.

## 🚀 Tecnologias e Inovações
- **Core**: Python 3.12 + Firebase Functions.
- **I.A. Engine**: **Gemini 3.1 Flash Lite** (Google Generative AI).
- **Vision AI**: Extração inteligente de dados a partir de fotos de redes sociais (Instagram/Facebook).
- **PDF Extraction**: Processamento de tabloides digitais e encartes semanais.
- **API Tracking**: Consumo direto de APIs GraphQL e REST para máxima performance.

## 📂 Estrutura do Projeto
- `/functions`: Código principal das Cloud Functions e lógica dos scrapers.
- `/docs`: Documentação técnica detalhada de cada supermercado.
- `/docs/scrapers`: Guia de implementação e manutenção de cada robô.
- `/scripts`: Utilitários de validação automática para teste dos robôs.

## ✅ Supermercados Integrados
- [x] **Seja Econômico**: API Direta.
- [x] **Atacadão**: API GraphQL (Regionalizado).
- [x] **Guerreirão (AM)**: HTML Scraping (SEO).
- [x] **Mix Mateus**: Híbrido (API + Gemini 3.1 PDF).
- [x] **Guerreirão (BR)**: Visão Computacional (Gemini 3.1 Vision).

## 🛠️ Como Testar
Para validar qualquer scraper sem precisar do App, use os scripts na pasta `/scripts`:
```bash
functions/venv/bin/python3 scripts/validador_mateus.py
```

---
**Desenvolvido com Antigravity (Google DeepMind)** 🦾🤖
