# Welcome to Cloud Functions for Firebase for Python!
# To get started, simply uncomment the below code or create your own.
# Deploy with `firebase deploy`

import os
import re
import json
import requests
import tempfile
import time
from datetime import datetime, timedelta
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from google.cloud.firestore_v1.base_query import FieldFilter

# Configuração global para evitar crash de rede no macOS (Segmentation Fault / _scproxy)
# Desativa a detecção automática de proxy do sistema que causa o crash no Firebase Emulator
os.environ["no_proxy"] = "*"
session = requests.Session()
session.trust_env = False

initialize_app()

# Lazy loading para o Firestore (evita crash de rede na inicialização do módulo)
_db_cache = None
def get_db():
    global _db_cache
    if _db_cache is None:
        _db_cache = firestore.client()
    return _db_cache

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
        resp = session.get(url, timeout=5)
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

    # --- FILTRO DE CATEGORIAS E PALAVRAS PROIBIDAS ---
    
    # 1. Bloqueio por Categoria (Whitelist de Supermercado)
    # Se a I.A. classificar como algo fora do escopo, bloqueamos preventivamente.
    categorias_proibidas = [
        "BAZAR", "ELETRÔNICOS", "ELETRO", "MODA", "VESTUÁRIO", 
        "AUTOMOTIVO", "BRINQUEDOS", "FERRAMENTAS", "MÓVEIS", "CASA"
    ]
    if categoria.upper() in categorias_proibidas:
        print(f"  🚫 Oferta bloqueada por CATEGORIA PROIBIDA: {categoria} - {nome}")
        return {"produto_id": produto_id, "salvo": False, "motivo": "categoria_proibida"}

    # 2. Lista de Palavras Proibidas (Safety Net)
    palavras_proibidas = [
        # Bebidas Alcoólicas
        "cerveja", "whisky", "whiskey", "vodka", "vodca", "gin", "vinho", 
        "chopp", "cachaça", "licor", "tequila", "rum", "ice", "skol", 
        "brahma", "heineken", "budweiser", "spaten", "amstel", "corona",
        "stella", "antarctica", "itaipava", "schin", "kaiser", "bavaria",
        "campari", "absolut", "smirnoff", "chandon", "espumante", "champagne",
        
        # Eletrônicos e Eletrodomésticos
        "aspirador", "liquidificador", "celular", "smartphone", "televisor", "smart tv", 
        "batedeira", "air fryer", "microondas", "lavadora", "geladeira", "fogao", "fogão", 
        "ventilador", "notebook", "tablet", "ferro de passar", "sanduicheira", "grill", 
        "smartwatch", "eletro", "fone", "carregador", "caixa de som", "furadeira", 
        "parafusadeira", "micro-ondas", "secador", "prancha",
        
        # Bazar, Moda e Diversos (Não-Alimentares)
        "pneu", "bicicleta", "moto", "carro", "bazar", "sandalia", "chinelo", "tenis", 
        "sapato", "mochila", "bolsa", "varal", "mop", "vassoura", "balde", "escada",
        "brinquedo", "boneca", "carrinho", "jogo", "bingo", "vestuario", "roupa", 
        "camiseta", "bermuda", "calca", "meia", "mesa", "cadeira", "armario", 
        "guarda-roupa", "colchao", "panela", "frigideira", "lampada", "lâmpada", 
        "pilha", "bateria", "churrasqueira"
    ]
    nome_lower = nome.lower()
    
    import re
    # Usa delimitadores de palavra (\b) para evitar bloqueios indevidos (ex: não bloquear 'mousse' por 'meia')
    if any(re.search(rf'\b{palavra}\b', nome_lower) for palavra in palavras_proibidas):
        print(f"  🚫 Oferta bloqueada pelo Filtro de Palavras: {nome}")
        return {"produto_id": produto_id, "salvo": False, "motivo": "palavra_proibida"}

    # --- UPSERT em /produtos ---
    ref_produto = get_db().collection("produtos").document(produto_id)
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
    ofertas_duplicadas = get_db().collection("ofertas").where(
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
    get_db().collection("ofertas").add({
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

        hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Busca todas as ofertas criadas hoje (simplificado para evitar erro de índice composto)
        query = get_db().collection("ofertas").where(
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


        query = get_db().collection("ofertas").where(
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
        response = session.get(url, headers=headers, timeout=15)
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

@https_fn.on_request()
def buscar_encarte_atacadao(req: https_fn.Request) -> https_fn.Response:
    """
    Fase 2: Extração Direta (Atacadão Icoaraci).
    Consome o catálogo via GraphQL com regionalização.
    """
    import base64
    
    url_api = "https://www.atacadao.com.br/api/graphql"
    seller_id = "atacadaobr153" # ID da loja Belém (Icoaraci/Augusto Montenegro)
    region_id = base64.b64encode(f"SW#{seller_id}".encode()).decode()
    
    channel = {
        "salesChannel": "1",
        "seller": seller_id,
        "regionId": region_id
    }
    
    variables = {
        "first": 40,
        "after": "0",
        "sort": "score_desc",
        "term": "", # Busca vazia traz o catálogo geral
        "selectedFacets": [
            {"key": "region-id", "value": region_id},
            {"key": "channel", "value": json.dumps(channel)},
            {"key": "locale", "value": "pt-BR"},
            {"key": "productClusterIds", "value": "312"} # Cluster de Ofertas
        ]
    }
    
    query = """
    query ProductsQuery($term: String, $selectedFacets: [SelectedFacetInput], $first: Int, $after: String, $sort: String) {
      products(term: $term, selectedFacets: $selectedFacets, first: $first, after: $after, sort: $sort) {
        edges {
          node {
            name
            brand {
              brandName
            }
            image {
              url
            }
            offers {
              offers {
                price
              }
              lowPrice
            }
          }
        }
      }
    }
    """
    
    params = {
        "operationName": "ProductsQuery",
        "variables": json.dumps(variables),
        "query": query
    }
    
    # 2. Chamada à API (Simulação de GET como o site faz)
    try:
        response = session.get(url_api, params=params)
        response.raise_for_status()
        dados = response.json()
        products = dados.get("data", {}).get("products", {}).get("edges", [])
        
        itens_extraidos = []
        
        for p_edge in products:
            try:
                node = p_edge.get("node", {})
                nome = node.get("name")
                marca = node.get("brand", {}).get("brandName", "")
                
                # No GraphQL GET, o formato da imagem pode variar
                img_data = node.get("image", [])
                if isinstance(img_data, list) and len(img_data) > 0:
                    imagem = img_data[0].get("url", "")
                else:
                    imagem = node.get("image", {}).get("url", "")
                
                # Pegando o preço da primeira oferta disponível
                offers = node.get("offers", {}).get("offers", [])
                if offers:
                    preco = float(offers[0].get("price", 0))
                else:
                    preco = float(node.get("offers", {}).get("lowPrice", 0))
                
                if preco > 0:
                    itens_extraidos.append({
                        "produto": f"{nome} {marca}".strip(),
                        "preco": preco,
                        "unidade": "un",
                        "categoria": "Geral",
                        "imagem": imagem,
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
                    supermercado_id="atacadao-icoaraci",
                    loja="Atacadão (Belém)",
                    metodo="api_graphql",
                    imagem_api=item.get("imagem", ""),
                    validade=item.get("validade")
                )
            except Exception as e_save:
                print(f"AVISO FIRESTORE - Erro ao salvar '{item['produto']}': {e_save}")

        return https_fn.Response(
            json.dumps({
                "sucesso": True,
                "loja": "Atacadão (Belém)",
                "metodo": "API GraphQL Direta",
                "quantidade": len(itens_extraidos),
                "itens": itens_extraidos
            }, ensure_ascii=False),
            mimetype="application/json"
        )

    except Exception as e:
        return https_fn.Response(
            json.dumps({"sucesso": False, "erro": str(e)}),
            mimetype="application/json", status=500
        )

@https_fn.on_request(secrets=["GEMINI_API_KEY"])
def buscar_encarte_assai(req: https_fn.Request) -> https_fn.Response:
    """
    NOVO: Extração automatizada via Site Oficial do Assaí.
    Captura os IDs de campanha/cluster e processa o encarte digital.
    """
    client = get_gemini_client()
    url_json = "https://www.assai.com.br/sites/default/files/static/ofertas_assai.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        # 1. Buscar metadados da oferta (JSON)
        id_oferta = None
        try:
            resp = session.get(url_json, headers=headers, timeout=10)
            if resp.status_code == 200:
                dados = resp.json()
                for o in dados.get("ofertas", []):
                    if "AUGUSTO MONTENEGRO" in o.get("loja", "").upper():
                        id_oferta = o.get("id_oferta")
                        break
        except Exception as e_json:
            print(f"AVISO: Falha ao ler JSON do Assaí: {e_json}")

        # Fallback 1: Tentar extrair do HTML da página da loja
        if not id_oferta:
            try:
                url_loja = "https://www.assai.com.br/ofertas/para/assai-augusto-montenegro"
                resp_loja = session.get(url_loja, headers=headers, timeout=15)
                if resp_loja.status_code == 200:
                    import re
                    # Procura por campaignId e clusterId no HTML (drupalSettings)
                    camp_match = re.search(r'"campaignId":\s*(\d+)', resp_loja.text)
                    clust_match = re.search(r'"clusterId":\s*(\d+)', resp_loja.text)
                    if camp_match and clust_match:
                        campanha = camp_match.group(1)
                        cluster = clust_match.group(1)
                        id_oferta = f"{campanha}-{cluster}"
            except Exception as e_html:
                print(f"AVISO: Falha ao fazer scrape do HTML do Assaí: {e_html}")

        # Fallback 2: IDs Estáticos (Última tentativa)
        if not id_oferta:
            campanha, cluster = "46503", "63"
        else:
            campanha, cluster = id_oferta.split("-")
        
        # 2. Montar URLs das páginas do encarte (geralmente de 1 a 6 páginas)
        imagens_encarte = []
        for i in range(1, 11): # Tenta até 10 páginas
            url_img = f"https://d2q57q7k4hzryv.cloudfront.net/RPA/v3/{campanha}/campanha-{campanha}-cluster-{cluster}-pagina-{i}.jpeg"
            
            # Usar GET com timeout curto para verificar existência (CloudFront às vezes barra HEAD)
            try:
                check = session.get(url_img, headers=headers, timeout=5, stream=True)
                if check.status_code == 200:
                    imagens_encarte.append(url_img)
                else:
                    break
            except:
                break

        if not imagens_encarte:
            return https_fn.Response("Nenhuma imagem de encarte encontrada para o Assaí.", status=404)

        # 3. Processar via Gemini Vision
        gemini_parts = []
        for url in imagens_encarte:
            img_data = session.get(url).content
            gemini_parts.append(types.Part.from_bytes(data=img_data, mime_type="image/jpeg"))

        prompt = """
        Analise o encarte do Assaí Atacadista e extraia os produtos de supermercado.
        FOCO: Alimentos, Higiene, Limpeza e Bebidas Não-Alcoólicas.
        IGNORE: Bebidas Alcoólicas (Cerveja, Vinho, etc.) e itens de Bazar (Eletrônicos, Eletro, Moda).
        Retorne APENAS o JSON puro no formato:
        {"itens": [{"produto": "NOME", "preco": 0.0, "unidade": "un", "categoria": "CATEGORIA"}]}
        """
        gemini_parts.append(prompt)

        response_gemini = client.models.generate_content(
            model="gemini-3.1-flash-image-preview", # Atualizado para o motor visual 3.1
            contents=gemini_parts
        )

        # 4. Parse e Salvar no Firestore
        try:
            texto_limpo = response_gemini.text.replace("```json", "").replace("```", "").strip()
            resultado = json.loads(texto_limpo)
            itens = resultado.get("itens", [])

            for item in itens:
                salvar_produto_e_oferta(
                    nome=item["produto"],
                    preco=item["preco"],
                    unidade=item["unidade"],
                    categoria=item["categoria"],
                    supermercado_id="assai",
                    loja="Assaí Atacadista",
                    metodo="site_tabloide",
                    imagem_api=""
                )

            return https_fn.Response(
                json.dumps({"sucesso": True, "loja": "Assaí", "quantidade": len(itens), "itens": itens}, ensure_ascii=False),
                mimetype="application/json"
            )
        except Exception as e_parse:
            return https_fn.Response(f"Erro no parse do Gemini: {str(e_parse)}", status=500)

    except Exception as e:
        return https_fn.Response(f"Erro no scraper do Assaí: {str(e)}", status=500)

@https_fn.on_request()
def buscar_encarte_economico(req: https_fn.Request) -> https_fn.Response:
    """
    Fase 3: Extração via API VipCommerce (Seja Econômico).
    Consome o endpoint oficial de OFERTAS da plataforma.
    """
    org_id = "315"
    filial_id = "1"
    cd_id = "1"
    
    # URL da vitrine de ofertas oficial
    url_api = f"https://services.vipcommerce.com.br/api-admin/v1/org/{org_id}/filial/{filial_id}/centro_distribuicao/{cd_id}/loja/produtos/em-oferta"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.grupoeconomico.com.br/ofertas",
        "Origin": "https://www.grupoeconomico.com.br",
        "DomainKey": "grupoeconomico.com.br",
        "OrganizationId": org_id,
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NzY3MTc0ODMsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMzE1In0.VsuwHCwfq-CF9yUzkGv6ekV--zAMmtWtPm-H6dbazQvC6GYp5spDx32GlWJEogReqDKU_TWscSNRW070elQDPA"
    }

    try:
        # Pegando a primeira página de ofertas (geralmente tem cerca de 40-50 itens por página)
        params = {"page": "1"}
        response = session.get(url_api, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        dados_puros = response.json()
        
        # LOG DE DEPURAÇÃO: Isso vai aparecer no seu terminal
        print(f"DEBUG ECONÔMICO - Chaves encontradas: {list(dados_puros.keys())}")
        
        # A VipCommerce varia: pode estar em 'data', 'produtos', ou ser uma lista direta
        produtos = []
        if isinstance(dados_puros, list):
            produtos = dados_puros
        elif "data" in dados_puros:
            produtos = dados_puros["data"]
            # Se for um dicionário com 'produtos' dentro
            if isinstance(produtos, dict):
                produtos = produtos.get("produtos", produtos.get("itens", []))
        elif "produtos" in dados_puros:
            produtos = dados_puros["produtos"]
        
        itens_extraidos = []
        
        # Se produtos for um dicionário (paginação), pegamos a lista real
        if isinstance(produtos, dict) and "items" in produtos:
            produtos = produtos["items"]
        elif isinstance(produtos, dict) and "produtos" in produtos:
            produtos = produtos["produtos"]

        if not isinstance(produtos, list):
            print(f"DEBUG ECONÔMICO - Estrutura inesperada: {type(produtos)}")
            produtos = []

        for p in produtos:
            try:
                # Na VipCommerce o nome costuma ser 'descricao'
                nome = p.get("descricao") or p.get("nome") or p.get("produto") or ""
                preco = float(p.get("preco_venda") or p.get("preco") or 0)
                
                if p.get("preco_promocional") and float(p.get("preco_promocional")) > 0:
                    preco = float(p.get("preco_promocional"))
                
                # Reconstruindo a URL da imagem (VipCommerce CDN)
                img_file = p.get("imagem_principal") or p.get("imagem") or ""
                imagem = f"https://static.vipcommerce.com.br/img/produtos/{org_id}/v/{img_file}" if img_file else ""
                
                unidade = p.get("unidade", "un")
                
                if preco > 0 and nome:
                    itens_extraidos.append({
                        "produto": nome.strip(),
                        "preco": preco,
                        "unidade": unidade.lower(),
                        "categoria": "Geral",
                        "imagem": imagem,
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
                    supermercado_id="seja-economico-am",
                    loja="Seja Econômico",
                    metodo="api_vipcommerce",
                    imagem_api=item.get("imagem", ""),
                    validade=item.get("validade")
                )
            except Exception as e_save:
                print(f"AVISO FIRESTORE - Erro ao salvar '{item['produto']}': {e_save}")

        return https_fn.Response(
            json.dumps({
                "sucesso": True,
                "loja": "Seja Econômico",
                "metodo": "API VipCommerce",
                "quantidade": len(itens_extraidos),
                "itens": itens_extraidos
            }, ensure_ascii=False),
            mimetype="application/json"
        )

    except Exception as e:
        return https_fn.Response(
            json.dumps({"sucesso": False, "erro": str(e)}),
            mimetype="application/json", status=500
        )

@https_fn.on_request()
def buscar_encarte_mateus(req: https_fn.Request) -> https_fn.Response:
    """
    Fase 1 Definitiva (O Garimpo Perfeito):
    Extração da lista de encartes atacando diretamente a API nativa invisível do site.
    """
    
    # O Santo Graal interceptado (Removido filtro de marca para capturar todos os encartes como 'Derruba Preço')
    url_mestra_api = "https://ofertasmateus.com/api-proxy.php?endpoint=%2Fencartes%2Fpa%2Fananindeua%2Fmateus-jaderlandia"
    
    try:
        # Puxando o tesouro da API
        response = session.get(url_mestra_api)
        response.raise_for_status()
        
        dados_puros = response.json()
        
        # Fase 1.1: Organizando a Escalabilidade (Deduplicação Inteligente com Verificação de Link)
        encartes_unicos = {}
        
        for item in dados_puros.get("data", []):
            titulo = item.get("descricao")
            if not titulo:
                continue
            
            url_absoluta = "https://ofertasmateus.com/api-proxy.php?file=" + item["arquivo"]
            
            # Se o título já existe, verificamos se o novo link é válido antes de substituir
            if titulo in encartes_unicos:
                try:
                    # Checagem HEAD ultra-rápida para garantir que o PDF existe
                    check = session.head(url_absoluta, timeout=5)
                    if check.status_code != 200:
                        print(f"⚠️ Mateus API retornou link quebrado para '{titulo}'. Mantendo versão anterior.")
                        continue
                except Exception as e_head:
                    print(f"⚠️ Erro ao validar link de '{titulo}': {e_head}")
                    continue
            
            encartes_unicos[titulo] = {
                "id_rastreio": item.get("id_encarte"),
                "marca": item.get("marca"),
                "titulo": titulo,
                "download_link": url_absoluta,
                "data_inicio_banco": item.get("inicio"),
                "data_inicio_tela": item.get("inicial"),
                "data_vencimento_banco": item.get("validade"),
                "data_vencimento_tela": item.get("valido")
            }
        
        catalogo_de_pdfs = list(encartes_unicos.values())
        
        # Devolvemos ao navegador a lista polida e finalizada, pronta para a Inteligência Artificial
        dados_retorno = {
            "sucesso": True,
            "mensagem": "Fase 1 estruturada pro aplicativo. Array escalável pronto!",
            "quantidade_atual": len(catalogo_de_pdfs),
            "catalogo": catalogo_de_pdfs
        }
            
        return https_fn.Response(
            json.dumps(dados_retorno),
            mimetype="application/json",
            headers={"Content-Type": "application/json; charset=utf-8"}
        )

    except Exception as e:
        return https_fn.Response(
            json.dumps({
                "sucesso": False,
                "erro": "Tentativa Frustrada. Detalhe: " + str(e)
            }),
            mimetype="application/json",
            status=500
        )

@https_fn.on_request(timeout_sec=540, memory=options.MemoryOption.GB_1, secrets=["GEMINI_API_KEY"])
def extrair_dados_encarte(req: https_fn.Request) -> https_fn.Response:
    """
    Fase 2: O Cérebro (Gemini 3.1 Flash Lite).
    Recebe um link de PDF, processa via IA e retorna JSON estruturado.
    """
    client = get_gemini_client()
    
    # 1. Pegar a URL do PDF da requisição
    link_pdf = ""
    if req.method == 'POST':
        data = req.get_json(silent=True)
        if data:
            link_pdf = data.get("url")
    else:
        link_pdf = req.args.get("url")

    if not link_pdf:
        return https_fn.Response(
            json.dumps({"sucesso": False, "erro": "URL do PDF não fornecida."}),
            mimetype="application/json", status=400
        )

    try:
        # 2. Download temporário do arquivo
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            response = session.get(link_pdf, timeout=30)
            response.raise_for_status()
            tmp_file.write(response.content)
            tmp_path = tmp_file.name

        try:
            # 3. Usar o Cliente Gemini Global (já configurado no topo do arquivo)
            
            # 4. Upload do arquivo para a API do Google
            print(f"DEBUG GEMINI - Iniciando upload do arquivo: {tmp_path}")
            try:
                uploaded_file = client.files.upload(file=tmp_path)
                print(f"DEBUG GEMINI - Upload concluído com sucesso: {uploaded_file.name}")
            except Exception as e:
                print(f"❌ ERRO GEMINI - Falha no upload: {str(e)}")
                raise e

            # 5. Roteamento e Prompt
            modelo_escolhido = "gemini-3.1-flash-lite"
            prompt_instrucao = """
            Você é um assistente de elite para extração de dados de encartes de supermercado.
            Sua missão é extrair TODOS os produtos e ofertas presentes no PDF anexado.
            
            FOCO PRINCIPAL: 
            Todos os itens de supermercado devem ser extraídos (Alimentação, Mercearia, Hortifruti, Carnes, Higiene, Limpeza, etc.).
            
            REGRAS DE OURO:
            1. Extraia o máximo de itens possível.
            2. Se houver preço de "Leve 3 Pague 2" ou "Preço Clube", use o preço unitário principal.
            3. RESTRIÇÃO CRÍTICA: IGNORE e NÃO extraia Bebidas Alcoólicas (Cervejas, Vinhos, Destilados, etc.).
            4. IGNORE também itens que não são de supermercado core: TVs, Celulares, Pneus, Roupas, Eletrodomésticos e Brinquedos.
            5. O campo 'preco' deve ser estritamente um NÚMERO (ex: 5.99).
            
            ESTRUTURA JSON OBRIGATÓRIA:
            {
                "itens": [
                    {
                        "produto": "NOME COMPLETO DO PRODUTO (Ex: Arroz Tio Urbano 5kg)",
                        "preco": 0.0,
                        "unidade": "un/kg/pacote",
                        "categoria": "Alimentos/Higiene/Limpeza/Hortifruti/Carnes",
                        "imagem": "URL se houver no PDF ou deixe vazio",
                        "validade": "Data de validade da oferta se encontrada"
                    }
                ]
            }
            Retorne APENAS o JSON puro, sem comentários ou markdown.
            """

            # 6. Gerar o Conteúdo
            print(f"DEBUG GEMINI - Invocando modelo {modelo_escolhido} para extração de dados...")
            tempo_invocacao = time.time()
            try:
                response_gemini = client.models.generate_content(
                    model=modelo_escolhido,
                    contents=[uploaded_file, prompt_instrucao],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
            except Exception as e:
                print(f"❌ ERRO GEMINI - Falha na geração de conteúdo: {str(e)}")
                raise e

            # 7. Limpeza e Retorno
            tempo_extraido = time.time()
            print(f"DEBUG GEMINI - Resposta da IA recebida em {tempo_extraido - tempo_invocacao:.2f}s.")
            
            try:
                texto_limpo = response_gemini.text.strip()
                if texto_limpo.startswith("```json"):
                    texto_limpo = texto_limpo.replace("```json", "").replace("```", "").strip()
                
                dados_extraidos = json.loads(texto_limpo)
            except Exception as e_json:
                print(f"❌ ERRO JSON - Falha ao decodificar resposta da IA: {str(e_json)}")
                print(f"DEBUG BRUTO - Resposta: {response_gemini.text[:500]}...")
                raise e_json
            
            itens = dados_extraidos.get("itens", [])
            print(f"DEBUG GEMINI - Extração concluída: {len(itens)} itens encontrados.")
            
            if not itens:
                print("⚠️ AVISO - IA retornou 0 itens. Resposta completa para debug:")
                print(json.dumps(dados_extraidos, indent=2))

            # --- Parâmetros de contexto (qual loja este PDF pertence) ---
            supermercado_id = ""
            loja_nome = ""
            if req.method == 'POST':
                body = req.get_json(silent=True) or {}
                supermercado_id = body.get("supermercado_id", "mateus-jaderlandia")
                loja_nome = body.get("loja", "Mix Mateus (Jaderlândia)")
            else:
                supermercado_id = req.args.get("supermercado_id", "mateus-jaderlandia")
                loja_nome = req.args.get("loja", "Mix Mateus (Jaderlândia)")

            # --- SALVAR NO FIRESTORE (OTIMIZADO COM BATCH) ---
            salvos = 0
            ignorado_filtro = 0
            
            db_conn = get_db()
            batch = db_conn.batch()
            
            # Filtro de categorias proibidas
            categorias_proibidas = ["BAZAR", "ELETRÔNICOS", "ELETRO", "MODA", "VESTUÁRIO", "AUTOMOTIVO", "BRINQUEDOS", "FERRAMENTAS", "MÓVEIS", "CASA"]

            for item in itens:
                try:
                    nome = item.get("produto", "")
                    categoria_item = item.get("categoria", "Geral")
                    
                    # 1. Validação de Preço
                    preco_raw = item.get("preco", 0)
                    preco = float(preco_raw) if preco_raw else 0
                    if preco <= 0: continue

                    # 2. Whitelist de Categoria
                    if categoria_item.upper() in categorias_proibidas:
                        ignorado_filtro += 1
                        continue

                    # 3. Preparar IDs
                    unidade = item.get("unidade", "un")
                    produto_id = normalizar_nome(nome, unidade)
                    
                    # --- OPERAÇÃO BATCH ---
                    ref_prod = db_conn.collection("produtos").document(produto_id)
                    batch.set(ref_prod, {
                        "nome": nome,
                        "unidade": unidade,
                        "categoria": categoria_item,
                        "atualizado_em": datetime.now()
                    }, merge=True)

                    # Referência da Oferta
                    hoje_str = datetime.now().strftime("%Y-%m-%d")
                    oferta_id = f"{supermercado_id}_{produto_id}_{hoje_str}"
                    ref_oferta = db_conn.collection("ofertas").document(oferta_id)
                    
                    batch.set(ref_oferta, {
                        "produto_id": produto_id,
                        "produto_nome": nome,
                        "supermercado_id": supermercado_id,
                        "loja": loja_nome,
                        "preco": preco,
                        "unidade": unidade,
                        "categoria": categoria_item,
                        "metodo": "gemini_pdf_batch",
                        "expira_em": datetime.now() + timedelta(days=7),
                        "criado_em": datetime.now()
                    }, merge=True)
                    
                    salvos += 1
                    
                    # Firestore batch limit is 500
                    if salvos % 200 == 0:
                        batch.commit()
                        batch = db_conn.batch()

                except Exception as e_item:
                    print(f"AVISO - Erro ao preparar item '{item.get('produto')}': {e_item}")

            # Commit final
            if salvos > 0:
                batch.commit()
                print(f"✅ BATCH COMPLETO - {salvos} itens processados para {loja_nome}.")

            # Capturar uso de tokens
            usage = response_gemini.usage_metadata

            # Adicionar metadados do cabeçalho
            resultado_final = {
                "sucesso": True,
                "loja": loja_nome,
                "metodo": "Gemini 3.1 Flash Lite",
                "quantidade": len(itens),
                "salvos_firestore": salvos,
                "uso_tokens": {
                    "total": usage.total_token_count if usage else 0,
                    "prompt": usage.prompt_token_count if usage else 0,
                    "resposta": usage.candidates_token_count if usage else 0
                },
                "itens": itens
            }

            return https_fn.Response(
                json.dumps(resultado_final, ensure_ascii=False),
                mimetype="application/json"
            )

        finally:
            # Limpar arquivo temporário
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        print(f"ERRO CRÍTICO GEMINI: {str(e)}")
        return https_fn.Response(
            json.dumps({"sucesso": False, "erro": str(e)}),
            mimetype="application/json", status=500
        )
@https_fn.on_request(timeout_sec=540, memory=options.MemoryOption.GB_1, secrets=["GEMINI_API_KEY"])
def extrair_dados_imagem(req: https_fn.Request) -> https_fn.Response:
    """
    Fase Especial: Visão Computacional (Gemini 3.1 Flash Lite).
    Recebe um link de imagem (Instagram/WhatsApp), processa via IA e retorna JSON.
    """
    client = get_gemini_client()
    
    try:
        # 1. Pegar a URL da imagem da requisição
        link_img = ""
        frames_b64 = []
        supermercado_id = ""
        post_id = ""
        loja_nome = ""

        if req.method == 'POST':
            data = req.get_json(silent=True) or {}
            link_img = data.get("url")
            frames_b64 = data.get("frames_b64", [])
            supermercado_id = data.get("supermercado_id", "")
            post_id = data.get("post_id", "")
            loja_nome = data.get("loja", "Extração via Visão (IA)")
        else:
            link_img = req.args.get("url")
            supermercado_id = req.args.get("supermercado_id", "")
            post_id = req.args.get("post_id", "")
            loja_nome = req.args.get("loja", "Extração via Visão (IA)")

        # --- TRAVA DE ECONOMIA (Check de Post ID antes da IA) ---
        if post_id and supermercado_id:
            hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Buscamos todas do dia e filtramos o post_id em memória para EVITAR ERRO DE ÍNDICE
            docs_hoje = get_db().collection("ofertas")\
                .where("criado_em", ">=", hoje_inicio)\
                .stream()
            
            post_ja_existe = any(d.to_dict().get("post_id") == post_id for d in docs_hoje)
            
            if post_ja_existe:
                print(f"💰 ECONOMIA: Post {post_id} já foi processado hoje. Pulando IA.")
                return https_fn.Response(
                    json.dumps({
                        "sucesso": True, 
                        "msg": "Post já processado hoje. (Economia de IA)",
                        "status": "ignorado_duplicado",
                        "resumo": {"extraidos": 0, "novos_salvos": 0, "duplicados": 0}
                    }, ensure_ascii=False),
                    mimetype="application/json"
                )

        if not link_img and not frames_b64:
            return https_fn.Response(
                json.dumps({"sucesso": False, "erro": "URL da imagem ou frames não fornecidos."}),
                mimetype="application/json", status=400
            )

        gemini_parts = []
        tmp_path = ""
        is_video = False
        
        if frames_b64:
            is_video = True
            import base64
            print(f"DEBUG VISION - Processando {len(frames_b64)} quadros de vídeo recebidos em base64.")
            for b64 in frames_b64:
                raw_bytes = base64.b64decode(b64)
                gemini_parts.append(types.Part.from_bytes(data=raw_bytes, mime_type="image/jpeg"))
        else:
            # 2. Download temporário da mídia (imagem estática original)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/*,video/*,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
                "Referer": "https://www.instagram.com/"
            }
            print(f"DEBUG VISION - Tentando baixar mídia (video/img)...")
            response = session.get(link_img, headers=headers, timeout=60)
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "")
            is_video = "video" in content_type or ".mp4" in link_img
            ext = ".mp4" if is_video else ".jpg"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name

            # 3. Upload do arquivo para a API do Google (Visão)
            tipo_nome = "vídeo" if is_video else "imagem"
            print(f"DEBUG VISION - Iniciando upload do {tipo_nome}: {tmp_path}")
            try:
                uploaded_file = client.files.upload(file=tmp_path)
                print(f"DEBUG VISION - Upload concluído: {uploaded_file.name}")
            except Exception as e:
                print(f"❌ ERRO VISION - Falha no upload: {str(e)}")
                raise e
            
            # Se for vídeo, precisamos esperar o Gemini processar o arquivo antes de inferir
            if is_video:
                import time
                print("DEBUG VISION - Vídeo detectado. Aguardando processamento da IA...")
                while uploaded_file.state.name == "PROCESSING":
                    print(".", end="", flush=True)
                    time.sleep(2)
                    # Atualiza o status do arquivo
                    uploaded_file = client.files.get(name=uploaded_file.name)
                print()
                
                if uploaded_file.state.name == "FAILED":
                    raise Exception("A IA falhou ao tentar processar o arquivo de vídeo.")
                print("DEBUG VISION - Vídeo processado com sucesso pela IA. Iniciando inferência.")
            
            gemini_parts.append(uploaded_file)

        try:
            # 4. Prompt de Visão estruturado com Filtro de Categorias RÍGIDO
            prompt_vision = """
            Você é um assistente de visão computacional especializado em varejo de supermercado.
            Analise a imagem(ns) ou os quadros de vídeo do encarte em anexo.
            
            FOCO TOTAL (Whitelist):
            Extraia APENAS itens de supermercado das categorias: ALIMENTAÇÃO, HIGIENE e LIMPEZA.
            
            BLOQUEIO ABSOLUTO (Ignore Completamente):
            1. Bebidas Alcoólicas (Cerveja, Vinho, Whisky, etc.).
            2. Eletrônicos e Eletrodomésticos (TV, Celular, Air Fryer, Ventilador, etc.).
            3. Bazar e Casa (Pneus, Ferramentas, Panelas, Móveis, Lâmpadas, etc.).
            4. Moda e Vestuário (Roupas, Calçados, Bolsas, etc.).
            5. Brinquedos e Papelaria.
            
            REGRAS ADICIONAIS:
            - Se encontrar itens proibidos, NÃO os inclua no JSON.
            - Extraia APENAS produtos que tenham o PREÇO CLARAMENTE VISÍVEL E LEGÍVEL.
            - Se a imagem mostrar um produto mas não exibir o preço exato, IGNORE-O.
            
            Padrão de saída JSON:
            {
                "itens": [
                    {"produto": "NOME", "preco": 0.0, "unidade": "un", "categoria": "CATEGORIA", "imagem": "", "validade": "DATA SE HOUVER"}
                ]
            }
            Retorne APENAS o JSON puro.
            """
            gemini_parts.append(prompt_vision)

            # 5. Roteamento (Utilizando 3.1-flash-image para máximo Q.I. Visual em fotos e vídeos)
            modelo_escolhido = "gemini-3.1-flash-image-preview"
            
            print(f"DEBUG VISION - Invocando modelo {modelo_escolhido} (Modo Vídeo: {is_video})...")
            try:
                response_gemini = client.models.generate_content(
                    model=modelo_escolhido,
                    contents=gemini_parts,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                print("DEBUG VISION - Resposta da IA (Visão) recebida.")
            except Exception as e:
                print(f"❌ ERRO VISION - Falha na geração de conteúdo: {str(e)}")
                raise e

            # 6. Limpeza e Retorno
            dados_extraidos = json.loads(response_gemini.text)
            usage = response_gemini.usage_metadata

            itens = dados_extraidos.get("itens", [])

            # --- SALVAR NO FIRESTORE (somente se supermercado_id for informado) ---
            salvos = 0
            duplicados = 0
            count_extraidos = 0
            erros_processamento = []

            if supermercado_id:
                print(f"DEBUG FIRESTORE - Iniciando salvamento de {len(itens)} itens para {supermercado_id}...")
                for item in itens:
                    try:
                        preco_raw = item.get("preco", 0)
                        if isinstance(preco_raw, str):
                            preco_raw = preco_raw.replace(",", ".")
                        preco = float(preco_raw) if preco_raw else 0
                        if preco <= 0:
                            continue
                        
                        count_extraidos += 1
                        res = salvar_produto_e_oferta(
                            nome=item.get("produto", ""),
                            preco=preco,
                            unidade=item.get("unidade", "un"),
                            categoria=item.get("categoria", "Geral"),
                            supermercado_id=supermercado_id,
                            loja=loja_nome,
                            metodo="gemini_vision",
                            imagem_api=item.get("imagem", ""),
                            validade=item.get("validade"),
                            post_id=post_id
                        )
                        
                        # Log detalhado para depuração no console do Firebase
                        print(f"  -> Processado: {item.get('produto')} | Res: {res}")

                        if res and res.get("duplicado"):
                            duplicados += 1
                        elif res and res.get("salvo"):
                            salvos += 1
                    except Exception as e_save:
                        err_msg = f"Erro em '{item.get('produto', '?')}': {str(e_save)}"
                        print(f"AVISO FIRESTORE - {err_msg}")
                        erros_processamento.append(err_msg)
            else:
                print("DEBUG FIRESTORE - supermercado_id não informado, pulando persistência.")

            resultado_final = {
                "sucesso": True,
                "loja": loja_nome,
                "status_final": "processado",
                "resumo": {
                    "extraidos": count_extraidos,
                    "novos_salvos": salvos,
                    "duplicados": duplicados,
                    "erros": erros_processamento[:5] # Mostra os primeiros 5 erros se houver
                },
                "uso_tokens": {
                    "total": usage.total_token_count
                }
            }

            return https_fn.Response(
                json.dumps(resultado_final, ensure_ascii=False),
                mimetype="application/json"
            )

        finally:
            # Limpar o arquivo da API do Gemini para não gastar a cota gratuita
            if 'uploaded_file' in locals() and uploaded_file:
                try:
                    client.files.delete(name=uploaded_file.name)
                except Exception:
                    pass

            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        print(f"💥 ERRO CRÍTICO VISION: {str(e)}")
        return https_fn.Response(
            json.dumps({"sucesso": False, "erro": str(e)}, ensure_ascii=False),
            mimetype="application/json", status=500
        )

# ==============================================================================
# AUTOMAÇÃO (CRON JOBS) — Atualização e Limpeza
# ==============================================================================
from firebase_functions import scheduler_fn

@scheduler_fn.on_schedule(schedule="0 10,14 * * *", timezone="America/Belem")
def atualizar_ofertas(event: scheduler_fn.ScheduledEvent) -> None:
    """
    CRON DIÁRIO: Roda às 10:00 e às 14:00.
    Chama as lógicas internas dos scrapers diretos e do Mateus para popular o Firestore
    após as lojas terem postado as ofertas do dia.
    """
    print("CRON: Iniciando atualização diária das ofertas...")
    
    # 1. Atacadão
    try:
        buscar_encarte_atacadao(None)
        print("CRON: Atacadão processado.")
    except Exception as e:
        print(f"CRON ERRO Atacadão: {e}")

    # 2. Econômico
    try:
        buscar_encarte_economico(None)
        print("CRON: Econômico processado.")
    except Exception as e:
        print(f"CRON ERRO Econômico: {e}")

    # 3. Guerreirão AM
    try:
        buscar_encarte_guerreirao(None)
        print("CRON: Guerreirão processado.")
    except Exception as e:
        print(f"CRON ERRO Guerreirão: {e}")

    # 4. Mateus (PDF via IA)
    try:
        # Usamos uma classe falsa para simular a requisição HTTP interna
        class DummyRequest:
            method = 'GET'
            args = {}
            def get_json(self, silent=True): return {}
            
        resp_mateus = buscar_encarte_mateus(DummyRequest())
        # Extrai o texto da resposta Flask/Functions
        dados_mateus = json.loads(resp_mateus.data.decode('utf-8'))
        
        if dados_mateus.get("sucesso") and dados_mateus.get("catalogo"):
            # Pegar o PDF mais recente
            link_pdf = dados_mateus["catalogo"][0]["download_link"]
            req_ext = DummyRequest()
            req_ext.args = {
                "url": link_pdf, 
                "supermercado_id": "mateus-jaderlandia", 
                "loja": "Mix Mateus (Jaderlândia)"
            }
            # Envia pro Gemini
            extrair_dados_encarte(req_ext)
            print("CRON: Mateus processado com sucesso.")
    except Exception as e:
        print(f"CRON ERRO Mateus: {e}")
        
    print("CRON: Atualização diária concluída.")


@scheduler_fn.on_schedule(schedule="every day 23:00", timezone="America/Belem")
def limpar_ofertas_expiradas(event: scheduler_fn.ScheduledEvent) -> None:
    """
    CRON NOTURNO: Roda às 23:00 PM.
    Vassoura: Apaga do Firestore todas as ofertas cujo 'expira_em' já passou,
    garantindo que o App nunca mostre oferta velha e poupando armazenamento gratuito.
    """

    
    print("CRON: Iniciando limpeza de ofertas expiradas...")
    db_cliente = firestore.client()
    
    # Busca ofertas que expiraram ANTES de agora
    query = db_cliente.collection("ofertas").where(
        filter=FieldFilter("expira_em", "<", datetime.now())
    )
    
    docs = query.stream()
    apagados = 0
    
    for doc in docs:
        try:
            doc.reference.delete()
            apagados += 1
        except Exception as e:
            print(f"CRON ERRO ao apagar documento {doc.id}: {e}")
            
    print(f"CRON: Limpeza concluída. {apagados} ofertas velhas foram apagadas.")
