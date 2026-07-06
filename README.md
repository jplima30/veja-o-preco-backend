# 🛒 Veja o Preço — Backend

<div align="center">

![Veja o Preço Banner](docs/banner.png)

<br/>

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-Cloud_Functions-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)
![Gemini](https://img.shields.io/badge/Gemini_AI-3.1-4285F4?style=for-the-badge&logo=google&logoColor=white)
![Firestore](https://img.shields.io/badge/Firestore-Database-FF6F00?style=for-the-badge&logo=firebase&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Automation-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)

**Backend inteligente que agrega ofertas de supermercados de Belém e Ananindeua em tempo real.**

[📖 Wiki](https://github.com/jplima30/veja-o-preco-backend/wiki) · [🏗️ Arquitetura](https://github.com/jplima30/veja-o-preco-backend/wiki/Arquitetura) · [✅ Checklist](https://github.com/jplima30/veja-o-preco-backend/wiki/Checklist-de-Implementacao) · [🛒 Supermercados](https://github.com/jplima30/veja-o-preco-backend/wiki/Supermercados)

</div>

---

## 📌 Sobre o Projeto

O **Veja o Preço** é um backend robusto desenvolvido em **Firebase Cloud Functions (Python)** para centralizar e comparar ofertas de supermercados da região metropolitana de Belém do Pará.

A arquitetura combina extração de dados via **APIs diretas**, **web scraping inteligente** e **Inteligência Artificial Generativa** (Gemini Vision + PDF), processando encartes digitais e publicações em redes sociais para entregar ofertas estruturadas ao App iOS consumidor.

---

## 🚀 Stack de Tecnologias

| Camada | Tecnologia | Função |
|---|---|---|
| **Core** | Python 3.12 + Firebase Functions | Runtime das Cloud Functions |
| **I.A. Engine** | Gemini 3.1 Flash Image / Flash Lite | Visão computacional em encartes e PDFs |
| **Automação** | Playwright (perfil persistente) | Captura de publicações em redes sociais |
| **Computer Vision** | EasyOCR | Triagem local de imagens antes da I.A. |
| **Banco de Dados** | Cloud Firestore | Persistência com deduplicação e histórico |
| **Segredos** | Google Secret Manager | Gestão segura de chaves de API |

---

## 🏗️ Fluxo de Funcionamento

```
┌─────────────┐    ┌───────────────┐    ┌──────────────────┐    ┌───────────────┐
│  Captura    │───▶│   Triagem     │───▶│    Extração      │───▶│  Persistência │
│             │    │               │    │                  │    │               │
│ Redes sociais│   │ EasyOCR filtra│   │ Gemini Vision    │    │ Firestore     │
│ APIs diretas │   │ imagens sem   │   │ extrai JSON      │    │ (deduplicado) │
│ Web scraping │   │ ofertas reais │   │ estruturado      │    │               │
└─────────────┘    └───────────────┘    └──────────────────┘    └───────────────┘
```

1. **Captura** — Robôs locais monitoram redes sociais (Instagram/WhatsApp) e consomem APIs das lojas.
2. **Triagem** — O EasyOCR filtra apenas imagens que contêm preços reais, economizando chamadas de API.
3. **Extração** — O Gemini processa os encartes e extrai dados estruturados em JSON.
4. **Persistência** — Dados são normalizados e salvos no Firestore seguindo o **[Contrato de Dados](https://github.com/jplima30/veja-o-preco-backend/wiki/Contrato-de-Dados)** do projeto.

---

## ✅ Supermercados Integrados

| Supermercado | Método de Extração | Status |
|---|---|---|
| **Mix Mateus** | API Oficial + Gemini (PDF) | ✅ Ativo |
| **Atacadão** | API GraphQL Regionalizada | ✅ Ativo |
| **Seja Econômico** | API VipCommerce Direta | ✅ Ativo |
| **Guerreirão (AM/BR)** | Scraping HTML + Vision AI | ✅ Ativo |
| **Assaí Atacadista** | Playwright + Vision AI | ✅ Ativo |
| **Líder & Formosa** | I.A. Multimodal (encarte PDF) | ✅ Ativo |

---

## 🛠️ Operação e Testes

> [!TIP]
> Para rodar os robôs ou validar os scrapers manualmente, consulte o **[Guia de Operação Local](https://github.com/jplima30/veja-o-preco-backend/wiki/Operacao-Local)**.

**Painel de Controle do Backend (Recomendado):**
O painel centraliza todas as operações diárias, curadorias de imagens, auditorias e testes:
```bash
python3 scripts/gerenciador.py
```

### 🧹 Higienização e Qualidade de Dados (CLI)
Dentro da **Categoria 4** do gerenciador, você encontra ferramentas inteligentes para curadoria:
* **Fuzzy Matching (`identificar_duplicatas.py`)** — Encontra produtos similares duplicados no Firestore e permite ignorar (adicionando à blacklist persistente `/duplicatas_ignoradas`) ou mesclar.
* **Mesclagem Cirúrgica (`mesclar_produtos.py`)** — Une dois produtos, transfere o histórico de ofertas, herda imagens de forma inteligente e registra a substituição na tabela de `/sinonimos`.
* **Auditor de Categorias (`auditar_categorias.py`)** — Analisa semântica em lote via IA (Gemini 3.1 Flash Lite) para identificar e propor correções de itens que caíram incorretamente em `ALIMENTOS`. Roda também de forma silenciosa no final do Cron diário.

**Deploy das Cloud Functions:**
```bash
firebase deploy --only functions
```

---

## 📚 Documentação Completa (Wiki)

| Página | Descrição |
|---|---|
| [🏠 Home](https://github.com/jplima30/veja-o-preco-backend/wiki) | Portal central da documentação |
| [🏗️ Arquitetura](https://github.com/jplima30/veja-o-preco-backend/wiki/Arquitetura) | Visão geral do ecossistema e decisões técnicas |
| [🗄️ Arquitetura Firestore](https://github.com/jplima30/veja-o-preco-backend/wiki/Arquitetura-Firestore) | Modelagem do banco e estratégias de persistência |
| [📋 Contrato de Dados](https://github.com/jplima30/veja-o-preco-backend/wiki/Contrato-de-Dados) | Formato JSON obrigatório para integração com o App iOS |
| [🛒 Supermercados](https://github.com/jplima30/veja-o-preco-backend/wiki/Supermercados) | Mapeamento das redes e métodos de extração |
| [✅ Checklist](https://github.com/jplima30/veja-o-preco-backend/wiki/Checklist-de-Implementacao) | Progresso das fases de implementação (Fases 1 a 7) |
| [💻 Operação Local](https://github.com/jplima30/veja-o-preco-backend/wiki/Operacao-Local) | Comandos práticos para rodar e testar o sistema |

---
