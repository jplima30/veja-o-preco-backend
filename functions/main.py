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

@https_fn.on_request()
def buscar_encarte_guerreirao(req: https_fn.Request) -> https_fn.Response:
    """
    Fase 2: Extração Direta (Guerreirão AM).
    Consome o portal QROfertas e extrai produtos via BeautifulSoup.
    """
    from bs4 import BeautifulSoup
    
    # URL principal é mais estável que o XHR para a lista completa
    url = "https://portal.qrofertas.com/meio-a-meio-o-guerreiro/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive"
    }
    
    try:
        # Acessando a página principal
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        itens_extraidos = []
        
        # O container principal dos cards na vitrine
        cards = soup.select(".boxProdutoEst, .product")
        
        for card in cards:
            try:
                # 1. Nome (Microdata ou Visual)
                nome_tag = card.select_one('[itemprop="name"]') or card.select_one(".nomeProduto span") or card.select_one(".nomeProdutoEst")
                if not nome_tag: continue
                nome = nome_tag.get_text(strip=True)
                
                # 2. Preço (Híbrido: Microdata -> Atributo -> Visual)
                preco_final = 0.0
                preco_tag = card.select_one('[itemprop="price"]')
                
                if preco_tag and (preco_tag.get("content") or preco_tag.get("value")):
                    valor = preco_tag.get("content") or preco_tag.get("value")
                    preco_final = float(valor.replace(",", "."))
                else:
                    # Fallback para o visual (.real + .cents)
                    real = card.select_one(".real")
                    cents = card.select_one(".cents")
                    if real:
                        v_real = "".join(filter(str.isdigit, real.get_text()))
                        v_cents = "".join(filter(str.isdigit, cents.get_text())) if cents else "00"
                        preco_final = float(f"{v_real}.{v_cents}")
                
                # 3. Unidade
                unidade_tag = card.select_one(".unidadeProduto") or card.select_one(".unidVendaEst")
                unidade = unidade_tag.get_text(strip=True).lower().replace("/", "") if unidade_tag else "un"
                
                # 4. Imagem
                img_tag = card.select_one('[itemprop="image"]') or card.select_one(".ftProduto img") or card.select_one(".img-fluid")
                imagem_url = img_tag.get("src") if img_tag else ""
                if imagem_url and imagem_url.startswith("//"):
                    imagem_url = "https:" + imagem_url
                
                if preco_final > 0:
                    itens_extraidos.append({
                        "produto": nome,
                        "preco": preco_final,
                        "unidade": unidade,
                        "categoria": "Geral",
                        "imagem": imagem_url,
                        "validade": None
                    })
            except:
                continue
        
        # --- SALVAR NO FIRESTORE ---
        for item in itens_extraidos:
            try:
                salvar_produto_e_oferta(
                    nome=item["produto"],
                    preco=item["preco"],
                    unidade=item["unidade"],
                    categoria=item["categoria"],
                    supermercado_id="guerreirao-am",
                    loja="Meio a Meio Guerreirão (AM)",
                    metodo="scraping_html",
                    imagem_api=item.get("imagem", ""),
                    validade=item.get("validade")
                )
            except Exception as e_save:
                print(f"AVISO FIRESTORE - Erro ao salvar '{item['produto']}': {e_save}")
        
        return https_fn.Response(
            json.dumps({
                "sucesso": True,
                "loja": "Meio a Meio Guerreirão (AM)",
                "metodo": "Scraping HTML (Híbrido)",
                "quantidade": len(itens_extraidos),
                "itens": itens_extraidos
            }, ensure_ascii=False),
            mimetype="application/json"
        )
    
    except Exception as e:
        return https_fn.Response(json.dumps({"sucesso": False, "erro": str(e)}), mimetype="application/json", status=500)
