# Welcome to Cloud Functions for Firebase for Python!
# To get started, simply uncomment the below code or create your own.
# Deploy with `firebase deploy`

import os
import re
import json
import requests
import tempfile
from datetime import datetime, timedelta
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

initialize_app()

# Cliente Firestore inicializado no nível do módulo (padrão recomendado)
db = firestore.client()

# Configuração do Gemini (Migrado para Secret Manager)
def get_gemini_client():
    """Retorna o cliente Gemini usando a chave do Secret Manager."""
    api_key = os.environ.get("GEMINI_API_KEY")
    return genai.Client(api_key=api_key)

# ==============================================================================
# MÓDULO FIRESTORE — Utilitários de Persistência
# ==============================================================================

def normalizar_nome(nome: str, unidade: str = "") -> str:
    """
    Gera um ID único e legível para um produto.
    Ex: "Arroz Agulhinha Tio Urbano", "5kg" → "arroz-agulhinha-tio-urbano-5kg"
    """
    texto = f"{nome} {unidade}".strip().lower()
    texto = re.sub(r'[áàãâä]', 'a', texto)
    texto = re.sub(r'[éèêë]', 'e', texto)
    texto = re.sub(r'[íìîï]', 'i', texto)
    texto = re.sub(r'[óòõôö]', 'o', texto)
    texto = re.sub(r'[úùûü]', 'u', texto)
    texto = re.sub(r'[ç]', 'c', texto)
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    texto = re.sub(r'\s+', '-', texto.strip())
    return texto


def buscar_imagem(nome_produto: str, imagem_api: str = "") -> str:
    """
    Busca a melhor imagem disponível para um produto em 3 camadas:
    1. Imagem da própria API da loja (se disponível)
    2. Open Food Facts (base de dados gratuita de produtos)
    3. String vazia (o App usará ícone de categoria como fallback)
    """
    # Camada 1: Imagem da API da loja
    if imagem_api and imagem_api.startswith("http"):
        return imagem_api

    # Camada 2: Open Food Facts
    try:
        url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={requests.utils.quote(nome_produto)}&search_simple=1&action=process&json=1&page_size=1"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            dados = resp.json()
            produtos = dados.get("products", [])
            if produtos:
                imagem = produtos[0].get("image_front_url", "")
                if imagem:
                    return imagem
    except Exception:
        pass  # Falha silenciosa — vai para Camada 3

    # Camada 3: Sem imagem (App usa ícone de categoria)
    return ""


def salvar_produto_e_oferta(
    nome: str,
    preco: float,
    unidade: str,
    categoria: str,
    supermercado_id: str,
    loja: str,
    metodo: str,
    imagem_api: str = "",
    marca: str = "",
    preco_antigo: float = None,
    validade: str = None,
    post_id: str = None
) -> dict:
    """
    Realiza o UPSERT do produto e registra a oferta no Firestore.
    - Se o produto não existe → cria em /produtos e busca imagem
    - Se já existe → apenas atualiza o timestamp
    - Sempre cria uma nova oferta em /ofertas com TTL de 7 dias
    """
    db = firestore.client()
    produto_id = normalizar_nome(nome, unidade)

    # --- FILTRO DE PALAVRAS PROIBIDAS (BEBIDAS ALCOÓLICAS) ---
    palavras_proibidas = [
        "cerveja", "whisky", "whiskey", "vodka", "vodca", "gin", "vinho", 
        "chopp", "cachaça", "licor", "tequila", "rum", "ice", "skol", 
        "brahma", "heineken", "budweiser", "spaten", "amstel", "corona",
        "stella", "antarctica", "itaipava", "schin", "kaiser", "bavaria",
        "campari", "absolut", "smirnoff", "chandon", "espumante", "champagne"
    ]
    nome_lower = nome.lower()
    
    import re
    # Usa delimitadores de palavra (\b) para evitar que 'gin' bloqueie 'original' ou 'ice' bloqueie 'spices'
    if any(re.search(rf'\b{palavra}\b', nome_lower) for palavra in palavras_proibidas):
        print(f"  🚫 Oferta bloqueada pelo Filtro do Backend: {nome}")
        return {"produto_id": produto_id, "salvo": False, "motivo": "bebida_alcoolica"}

    # --- UPSERT em /produtos ---
    ref_produto = db.collection("produtos").document(produto_id)
    doc_produto = ref_produto.get()

    if not doc_produto.exists:
        imagem_url = buscar_imagem(nome, imagem_api)
        ref_produto.set({
            "nome": nome,
            "marca": marca,
            "unidade": unidade,
            "categoria": categoria,
            "imagem_url": imagem_url,
            "criado_em": datetime.now(),
            "atualizado_em": datetime.now()
        })
    else:
        ref_produto.update({"atualizado_em": datetime.now()})

    # --- Calcular data de expiração da oferta ---
    if validade:
        # Tenta usar a data real extraída pela I.A.
        expira_em = datetime.now() + timedelta(days=7)  # fallback padrão
    else:
        expira_em = datetime.now() + timedelta(days=7)

    # --- DEDUPLICAÇÃO INTELIGENTE EM /ofertas ---
    ofertas_duplicadas = db.collection("ofertas").where(
        "produto_id", "==", produto_id
    ).where(
        "supermercado_id", "==", supermercado_id
    ).where(
        "preco", "==", preco
    ).where(
        "expira_em", ">=", datetime.now()
    ).limit(1).get()
    
    if ofertas_duplicadas:
        doc_duplicado = ofertas_duplicadas[0]
        if post_id and not doc_duplicado.to_dict().get("post_id"):
             doc_duplicado.reference.update({"post_id": post_id})
             print(f"  📝 Post ID atualizado para oferta existente: {nome}")
        
        print(f"  ⏭️ Oferta recusada pelo Banco (já existe e ainda é válida): {nome} a R$ {preco}")
        return {"produto_id": produto_id, "salvo": True, "duplicado": True}

    # --- Criar nova oferta em /ofertas ---
    db.collection("ofertas").add({
        "produto_id": produto_id,
        "produto_nome": nome,
        "supermercado_id": supermercado_id,
        "loja": loja,
        "preco": preco,
        "preco_antigo": preco_antigo,
        "unidade": unidade,
        "categoria": categoria,
        "metodo": metodo,
        "validade": validade,
        "post_id": post_id,
        "expira_em": expira_em,
        "criado_em": datetime.now()
    })

    return {"produto_id": produto_id, "salvo": True, "duplicado": False}
