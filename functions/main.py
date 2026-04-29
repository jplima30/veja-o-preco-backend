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




@https_fn.on_request()
def get_status_extracao(req: https_fn.Request) -> https_fn.Response:
    """
    Dashboard de Auditoria: Retorna a lista de post_ids processados hoje.
    Usado pelo script local para comparar o que já subiu para a nuvem.
    """
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Busca todas as ofertas criadas hoje (simplificado para evitar erro de índice composto)
        query = db.collection("ofertas").where(
            filter=FieldFilter("criado_em", ">=", hoje_inicio)
        )
        
        docs = query.stream()
        processados = {} # loja -> [post_ids]
        
        for doc in docs:
            dados = doc.to_dict()
            loja = dados.get("supermercado_id")
            pid = dados.get("post_id")
            
            # Filtra apenas quem tem post_id em memória
            if not pid:
                continue
            
            if loja not in processados:
                processados[loja] = set()
            processados[loja].add(pid)
            
        # Converte sets para listas para o JSON
        for loja in processados:
            processados[loja] = list(processados[loja])
            
        return https_fn.Response(
            json.dumps({"sucesso": True, "processados": processados}, ensure_ascii=False),
            mimetype="application/json"
        )
    except Exception as e:
        return https_fn.Response(json.dumps({"sucesso": False, "erro": str(e)}), status=500)

@https_fn.on_request()
def get_ofertas_do_dia(req: https_fn.Request) -> https_fn.Response:
    """
    Endpoint principal para o App iOS.
    Lê ofertas válidas (não expiradas) diretamente do Firestore.

    Parâmetros de query (todos opcionais):
        - categoria:      Filtra por categoria (Ex: Mercearia, Hortifruti)
        - supermercado_id: Filtra por loja (Ex: seja-economico-am, atacadao-icoaraci)
        - limite:          Máximo de resultados (padrão: 100)

    Exemplos:
        GET /get_ofertas_do_dia
        GET /get_ofertas_do_dia?categoria=Mercearia
        GET /get_ofertas_do_dia?supermercado_id=atacadao-icoaraci&limite=20
    """
    try:
        # Parâmetros opcionais
        categoria = req.args.get("categoria")
        supermercado_id = req.args.get("supermercado_id")
        limite = int(req.args.get("limite", 100))

        # Query base: apenas ofertas que ainda não expiraram
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = db.collection("ofertas").where(
            filter=FieldFilter("expira_em", ">=", datetime.now())
        )

        # Filtros opcionais
        if supermercado_id:
            query = query.where(
                filter=FieldFilter("supermercado_id", "==", supermercado_id)
            )

        # Executar query com limite
        docs = query.limit(limite).stream()

        # Montar a lista de ofertas
        ofertas = []
        for doc in docs:
            oferta = doc.to_dict()

            # Filtro de categoria em memória (Firestore limita queries compostas)
            if categoria and oferta.get("categoria", "").lower() != categoria.lower():
                continue

            ofertas.append({
                "produto": oferta.get("produto_nome", ""),
                "preco": oferta.get("preco", 0),
                "preco_antigo": oferta.get("preco_antigo"),
                "unidade": oferta.get("unidade", "un"),
                "categoria": oferta.get("categoria", "Geral"),
                "loja": oferta.get("loja", ""),
                "supermercado_id": oferta.get("supermercado_id", ""),
                "validade": oferta.get("validade"),
                "imagem": oferta.get("imagem", ""),
            })

        return https_fn.Response(
            json.dumps({
                "sucesso": True,
                "quantidade": len(ofertas),
                "filtros": {
                    "categoria": categoria,
                    "supermercado_id": supermercado_id,
                    "limite": limite
                },
                "ofertas": ofertas
            }, ensure_ascii=False, default=str),
            mimetype="application/json"
        )

    except Exception as e:
        return https_fn.Response(
            json.dumps({"sucesso": False, "erro": str(e)}),
            mimetype="application/json", status=500
        )
