"""
Script: seed_firestore.py
Objetivo: Criar a estrutura inicial correta do Firestore para o projeto "Veja o Preço".

ATENÇÃO: Este script APAGA as coleções antigas (supermercados, produtos, encartes)
         e recria tudo com a estrutura correta e padronizada.

Uso:
    cd /Users/jplima/Documents/veja-o-preco-backend
    source functions/venv/bin/activate
    python3 scripts/seed_firestore.py
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# ==============================================================================
# 1. INICIALIZAÇÃO DO FIREBASE ADMIN
# ==============================================================================
# Usa as credenciais padrão do ambiente (Firebase CLI já logado).
# Não precisa de arquivo de chave separado.

try:
    app = firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": "veja-o-preco"})

db = firestore.client()
print("✅ Firebase Admin inicializado com sucesso.")

# ==============================================================================
# 2. FUNÇÃO DE LIMPEZA
# ==============================================================================

def deletar_colecao(nome_colecao):
    """Deleta todos os documentos de uma coleção."""
    docs = db.collection(nome_colecao).stream()
    total = 0
    for doc in docs:
        doc.reference.delete()
        total += 1
    print(f"🗑️  Coleção '{nome_colecao}' limpa. ({total} documentos removidos)")

# ==============================================================================
# 3. DADOS DOS SUPERMERCADOS (ESTRUTURA CORRETA)
# ==============================================================================

SUPERMERCADOS = [
    {
        "id": "seja-economico-am",
        "nome": "Seja Econômico (Augusto Montenegro)",
        "slug": "seja-economico-am",
        "rede": "Grupo Econômico",
        "ativo": True,
        "dificuldade": "baixa",
        "metodo_extracao": "api_vipcommerce",
        "fontes": {
            "ecommerce": "https://www.grupoeconomico.com.br/",
            "instagram": "",
            "facebook": ""
        },
        "criado_em": datetime.now(),
        "atualizado_em": datetime.now()
    },
    {
        "id": "atacadao-ananindeua",
        "nome": "Atacadão Ananindeua",
        "slug": "atacadao-ananindeua",
        "rede": "Atacadão",
        "ativo": True,
        "dificuldade": "baixa",
        "metodo_extracao": "api_graphql",
        "fontes": {
            "ecommerce": "https://www.atacadao.com.br/catalogo",
            "instagram": "",
            "facebook": ""
        },
        "criado_em": datetime.now(),
        "atualizado_em": datetime.now()
    },
    {
        "id": "guerreirao-am",
        "nome": "Meio a Meio Guerreirão (AM)",
        "slug": "guerreirao-am",
        "rede": "Guerreirão",
        "ativo": True,
        "dificuldade": "baixa",
        "metodo_extracao": "html_scraping",
        "fontes": {
            "ecommerce": "https://portal.qrofertas.com/meio-a-meio-o-guerreiro/",
            "instagram": "",
            "facebook": ""
        },
        "criado_em": datetime.now(),
        "atualizado_em": datetime.now()
    },
    {
        "id": "mix-mateus-jaderlandia",
        "nome": "Mix Mateus Jaderlândia",
        "slug": "mix-mateus-jaderlandia",
        "rede": "Grupo Mateus",
        "ativo": True,
        "dificuldade": "media",
        "metodo_extracao": "api_pdf_gemini",
        "fontes": {
            "ecommerce": "https://ofertasmateus.com/pa/ananindeua/mateus-jaderlandia",
            "instagram": "",
            "facebook": ""
        },
        "criado_em": datetime.now(),
        "atualizado_em": datetime.now()
    },
    {
        "id": "guerreirao-br",
        "nome": "Meio a Meio Guerreirão (BR-316)",
        "slug": "guerreirao-br",
        "rede": "Guerreirão",
        "ativo": True,
        "dificuldade": "alta",
        "metodo_extracao": "vision_instagram",
        "fontes": {
            "ecommerce": "",
            "instagram": "https://www.instagram.com/mmguerreirao/",
            "facebook": ""
        },
        "criado_em": datetime.now(),
        "atualizado_em": datetime.now()
    },
    {
        "id": "lider-am",
        "nome": "Supermercados Líder (Augusto Montenegro)",
        "slug": "lider-am",
        "rede": "Grupo Líder",
        "ativo": True,
        "dificuldade": "alta",
        "metodo_extracao": "vision_instagram_facebook",
        "fontes": {
            "ecommerce": "",
            "instagram": "https://www.instagram.com/supermercadoslider/",
            "facebook": "https://www.facebook.com/lidersupermercado"
        },
        "criado_em": datetime.now(),
        "atualizado_em": datetime.now()
    },
    {
        "id": "formosa-am",
        "nome": "Super Formosa (Augusto Montenegro)",
        "slug": "formosa-am",
        "rede": "Grupo Formosa",
        "ativo": True,
        "dificuldade": "alta",
        "metodo_extracao": "vision_facebook",
        "fontes": {
            "ecommerce": "",
            "instagram": "",
            "facebook": "https://www.facebook.com/formosaoficial"
        },
        "criado_em": datetime.now(),
        "atualizado_em": datetime.now()
    },
    {
        "id": "assai-am",
        "nome": "Assaí Atacadista (Augusto Montenegro)",
        "slug": "assai-am",
        "rede": "Assaí",
        "ativo": True,
        "dificuldade": "media",
        "metodo_extracao": "hibrido_playwright_vision",
        "fontes": {
            "ecommerce": "https://www.assai.com.br/ofertas/para/assai-augusto-montenegro",
            "instagram": "https://www.instagram.com/assaiatacadistaoficial/",
            "facebook": ""
        },
        "criado_em": datetime.now(),
        "atualizado_em": datetime.now()
    }
]

# ==============================================================================
# 4. EXECUÇÃO DO SEED
# ==============================================================================

print("\n🚀 Iniciando criação da estrutura correta do Firestore...\n")

# Passo 1: Limpar coleções antigas
print("--- PASSO 1: Limpando coleções antigas ---")
deletar_colecao("supermercados")
deletar_colecao("produtos")
deletar_colecao("encartes")

# Passo 2: Criar supermercados com estrutura completa
print("\n--- PASSO 2: Criando /supermercados ---")
for sm in SUPERMERCADOS:
    doc_id = sm.pop("id")
    db.collection("supermercados").document(doc_id).set(sm)
    status = "✅" if sm["ativo"] else "⏳"
    print(f"  {status} {sm['nome']}")

# Passo 3: Criar coleções vazias com documento placeholder
print("\n--- PASSO 3: Criando estruturas de /produtos e /ofertas ---")
db.collection("produtos").document("_schema").set({
    "_info": "Coleção gerenciada automaticamente pelos scrapers.",
    "exemplo_campos": {
        "nome": "Arroz Agulhinha Tio Urbano",
        "marca": "Tio Urbano",
        "unidade": "5kg",
        "categoria": "Mercearia",
        "imagem_url": "",
        "criado_em": datetime.now(),
        "atualizado_em": datetime.now()
    }
})
print("  📦 /produtos — estrutura criada.")

db.collection("ofertas").document("_schema").set({
    "_info": "Coleção gerenciada automaticamente pelos scrapers.",
    "exemplo_campos": {
        "produto_id": "arroz-tio-urbano-5kg",
        "produto_nome": "Arroz Agulhinha Tio Urbano",
        "supermercado_id": "seja-economico-am",
        "loja": "Seja Econômico",
        "preco": 20.25,
        "preco_antigo": None,
        "unidade": "un",
        "categoria": "Mercearia",
        "metodo": "api_vipcommerce",
        "validade": None,
        "expira_em": datetime.now(),
        "criado_em": datetime.now()
    }
})
print("  🏷️  /ofertas — estrutura criada.")

print("\n🎉 Seed concluído! Firestore está com a estrutura correta.")
print("💡 Dica: Os documentos '_schema' são apenas referência — podem ser deletados depois.")
