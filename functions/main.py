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
    
    params = {
        "operationName": "ProductsQuery",
        "variables": json.dumps(variables)
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }

    try:
        response = requests.get(url_api, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        dados_puros = response.json()
        
        products = dados_puros.get("data", {}).get("search", {}).get("products", {}).get("edges", [])
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
            resp = requests.get(url_json, headers=headers, timeout=10)
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
                resp_loja = requests.get(url_loja, headers=headers, timeout=15)
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
                check = requests.get(url_img, headers=headers, timeout=5, stream=True)
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
            img_data = requests.get(url).content
            gemini_parts.append(types.Part.from_bytes(data=img_data, mime_type="image/jpeg"))

        prompt = """
        Analise o encarte do Assaí Atacadista e extraia os produtos de ALIMENTOS.
        Retorne APENAS o JSON puro no formato:
        {"itens": [{"produto": "NOME", "preco": 0.0, "unidade": "un", "categoria": "Geral"}]}
        """
        gemini_parts.append(prompt)

        response_gemini = client.models.generate_content(
            model="gemini-1.5-flash", # Usando 1.5 flash para estabilidade e custo
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
