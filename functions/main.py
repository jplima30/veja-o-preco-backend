# Welcome to Cloud Functions for Firebase for Python!
# To get started, simply uncomment the below code or create your own.
# Deploy with `firebase deploy`

import os
import re
import json
import requests
import tempfile
import time
import io
import difflib
import threading
import unicodedata
from PIL import Image
from datetime import datetime, timedelta
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore, storage
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

# Configuração do Gemini (Google Cloud Vertex AI)
def get_gemini_client():
    """Retorna o cliente Gemini conectado nativamente ao Google Cloud Vertex AI."""
    project_id = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "veja-o-preco"
    location = os.environ.get("GOOGLE_CLOUD_LOCATION") or "global"
    return genai.Client(vertexai=True, project=project_id, location=location)

# ==============================================================================
# MÓDULO FIRESTORE — Utilitários de Persistência
# ==============================================================================

def normalizar_unidade(unidade: str) -> str:
    """
    Padroniza unidades de medida comuns para evitar duplicações de cadastro.
    """
    u = unidade.strip().lower()
    if u in ("cada", "unidade", "unid", "und", "un"):
        return "un"
    if u in ("quilo", "kilo", "kg"):
        return "kg"
    if u in ("litro", "litros", "l"):
        return "l"
    if u in ("grama", "gramas", "gr", "g"):
        return "g"
    return u


def normalizar_categoria(categoria: str, nome: str = "") -> str:
    """
    Padroniza categorias de produtos para evitar duplicações de cadastro e alinhar com o App.
    Mapeia variações ortográficas e setores correlatos (como rotisseria -> PADARIA).
    Se o nome do produto contiver termos ou marcas estritamente da linha PET/veterinária,
    garante a atribuição imediata a PET, sobrepondo classificações genéricas como HIGIENE ou LIMPEZA.
    """
    if not categoria:
        categoria = "ALIMENTOS"
    c = categoria.strip().lower()
    n = nome.strip().lower() if nome else ""
    
    # 0. PET (Avaliar primeiro no nome e na categoria para evitar desvios para Higiene, Limpeza, Carnes, etc.)
    termos_pet = [
        "ração", "racao", "dog chow", "cat chow", "pedigree", "whiskas", "friskies", 
        "procão", "procao", "purina", "monello", "birbo", "granplus", "golden", "bomguy", 
        "nino dog", "chum", "adestrador", "tapete higiênico", "tapete higienico", "pet care", 
        "gato", "gatos", "cachorro", "cachorros", "filhote", "filhotes", "cão", "caes", "cao",
        "veterinário", "veterinario", "kdog", "k-dog", "sanol dog", "sanol", "petiscos pet",
        "bifinho", "bifinhos", "areia sanitária", "areia sanitaria", "sílica pet", "silica pet"
    ]
    # Checagem prioritária no NOME do produto
    if n and any(re.search(rf'\b{term}\b', n) for term in termos_pet):
        if not any(x in n for x in ["coração", "coracao"]):
            return "PET"

    # Checagem na categoria informada
    if any(re.search(rf'\b{term}\b', c) for term in termos_pet):
        # Evitar falsos positivos como corações de carne
        if not any(x in c for x in ["coração", "coracao"]):
            return "PET"
    
    # 1. Higiene / Limpeza baseados na categoria original do banco
    if any(x in c for x in ["limpeza", "detergente", "sabão", "sabao"]):
        return "LIMPEZA"
    if any(x in c for x in ["higiene", "perfumaria", "cosmético", "cosmetico", "shampoo", "sabonete"]):
        return "HIGIENE"

    # Exclusões de produtos industrializados/mercearia para evitar falsos positivos
    if any(term in c for term in ["farofa", "extrato", "molho", "sachê", "sache", "tempero", "caldo", "conserva"]):
        return "ALIMENTOS"

    # 2. BEBIDAS (Avaliar antes de Hortifruti para evitar que suco de uva vire Hortifruti)
    termos_bebidas = [
        "refrigerante", "coca-cola", "coca cola", "fanta", "guaraná", "guarana", "suco", 
        "del valle", "ades", "red bull", "monster", "bebida láctea", "bebida lactea", "gatorade", 
        "água mineral", "agua mineral", "h2oh", "tônica", "tonica"
    ]
    if any(re.search(rf'\b{term}\b', c) for term in termos_bebidas):
        if "lámen" in c or "lamen" in c or "miojo" in c:
            return "ALIMENTOS"
        return "BEBIDAS"

    # 3. FRIOS e LATICÍNIOS (Avaliar antes de Carnes/Hortifruti)
    termos_laticinios = [
        "leite", "queijo", "mussarela", "mucarela", "requeijão", "requeijao", 
        "iogurte", "yogurte", "manteiga", "margarina", "danone", "danoninho", 
        "refrigerado", "frios", "presunto", "apresuntado", "mortadela", "salame", 
        "peito de peru", "blanquet", "coalho", "ricota", "provolone", "parmesão", 
        "parmesao", "bebida láctea", "bebida lactea", "yakult", "chamyto", 
        "cream cheese", "creme de leite", "leite condensado", "leite fermentado"
    ]
    if any(re.search(rf'\b{term}\b', c) for term in termos_laticinios):
        # Evitar falsos positivos comuns
        if any(x in c for x in [
            "chocolate", "biscoito", "bolacha", "pão", "pao", "doce", 
            "rosas", "colônia", "colonia", "magnésia", "magnesia", "sabonete",
            "shampoo", "condicionador", "hidratante"
        ]):
            pass
        else:
            return "FRIOS_LATICINIOS"

    # 4. CARNES
    termos_carnes = [
        "carnes", "carne", "picanha", "alcatra", "músculo", "musculo", "peito de frango", "sobrecoxa", 
        "asa", "coração", "coracao", "linguiça", "linguica", "salsicha", "tambaqui", "peixe", 
        "filé", "file", "bovino", "suíno", "suino", "frango", "bacalhau", "costelinha", 
        "chouriço", "chourico", "pernil", "paleta"
    ]
    if any(re.search(rf'\b{term}\b', c) for term in termos_carnes):
        if "ração" in c or "racao" in c:
            return "ALIMENTOS"
        return "CARNES"
        
    # 4. HORTIFRUTI
    termos_horti = [
        "limão", "limao", "banana", "maçã", "maca", "uva", "abacaxi", "mamão", "mamao", 
        "laranja", "cebola", "alho", "tomate", "batata", "cenoura", "ovos", "ovo", "cheiro verde", 
        "coentro", "pimentão", "pimentao", "abóbora", "abobora", "morango", "melancia", 
        "alface", "repolho", "coentro", "cheiro-verde", "cebolinha",
        
        # Regionais (Pará/Norte)
        "maniva", "jambu", "mandioca", "macaxeira"
    ]
    if any(re.search(rf'\b{term}\b', c) for term in termos_horti):
        return "HORTIFRUTI"
        
    # 5. PADARIA
    termos_padaria = [
        "pão", "pao", "bisnaguinha", "bolo", "torta", "torrada", "croissant", 
        "pão de queijo", "pao de queijo", "brioche", "cookie", "donuts"
    ]
    if any(re.search(rf'\b{term}\b', c) for term in termos_padaria):
        if "bolota" in c:
            return "ALIMENTOS"
        return "PADARIA"
        
    if re.search(r'\bsalgado\b', c):
        if not any(x in c for x in ["amendoim", "camarão", "camarao", "peixe", "castanha"]):
            return "PADARIA"
            
    # 6. HIGIENE
    termos_higiene = [
        "shampoo", "sabonete", "creme dental", "pasta de dente", "colgate", "sensodyne", 
        "fio dental", "desodorante", "rexona", "nivea", "dove", "absorvente", "fralda", 
        "condicionador", "hidratante", "protetor solar", "óleo capilar", "oleo capilar", 
        "tintura", "maxton", "aparelho de barbear", "gillette", "listerine", "colônia", "colonia", "esmalte"
    ]
    if any(re.search(rf'\b{term}\b', c) for term in termos_higiene):
        return "HIGIENE"

    # 7. LIMPEZA
    termos_limpeza = [
        "detergente", "sabão", "sabao", "amaciante", "desinfetante", "lava-louças", "lavaloucas", 
        "clorox", "veja", "ypê", "ype", "omo", "brilhante", "tixan", "downy", "comfort", 
        "papel higiênico", "papel higienico", "esponja", "lã de aço", "la de aco", "bombril"
    ]
    if any(re.search(rf'\b{term}\b', c) for term in termos_limpeza):
        return "LIMPEZA"

    cat_upper = categoria.strip().upper()
    if cat_upper in {"CARNES", "HORTIFRUTI", "PADARIA", "BEBIDAS", "HIGIENE", "LIMPEZA", "FRIOS_LATICINIOS", "PET"}:
        return cat_upper

    return "ALIMENTOS"


def canonicizar_meta_termos(nome: str) -> str:
    """
    Padroniza variações semânticas de termos coletivos/promocionais de encarte
    (ex: 'vários tipos', 'diversos sabores', 'sabores sortidos') para a forma
    canônica 'vários sabores', evitando duplicidade de produtos mestres.
    """
    import re
    n = nome.strip()
    # 1. "vários tipos" / "diversos tipos" / "tipos variados" -> "vários sabores"
    n = re.sub(r'\b(v[aá]rios|diversos)\s+(tipos|modelos)\b', 'vários sabores', n, flags=re.IGNORECASE)
    n = re.sub(r'\b(tipos)\s+(variados|diversos|sortidos)\b', 'vários sabores', n, flags=re.IGNORECASE)
    
    # 2. "sabores sortidos" / "diversos sabores" / "sabores variados" -> "vários sabores"
    n = re.sub(r'\b(diversos)\s+(sabores)\b', 'vários sabores', n, flags=re.IGNORECASE)
    n = re.sub(r'\b(sabores)\s+(sortidos|variados|diversos)\b', 'vários sabores', n, flags=re.IGNORECASE)
    
    # 3. "aromas sortidos" / "diversas fragrâncias" / "várias fragrâncias" -> "várias fragrâncias"
    n = re.sub(r'\b(v[aá]rios|diversos)\s+(aromas)\b', 'várias fragrâncias', n, flags=re.IGNORECASE)
    n = re.sub(r'\b(aromas|fragr[aâ]ncias)\s+(sortidos|sortidas|variados|variadas|diversos|diversas)\b', 'várias fragrâncias', n, flags=re.IGNORECASE)
    
    return re.sub(r'\s+', ' ', n).strip()


# Tabela de apelidos do varejo: abreviaturas e formas curtas -> forma canônica.
# Aplicada no nome do produto ANTES de gerar o ID, nos dois caminhos de gravação
# (visão e lote PDF passam por limpar_nome_promocional). Novas entradas não
# exigem mudança de lógica. Mantida pequena e conservadora de propósito.
ALIAS_TERMO = [
    (r'\bc\/s\b\.?', 'com sal'),
    (r'\bs\/s\b\.?', 'sem sal'),
    (r'\bc\/', 'com '),
    (r'\bs\/', 'sem '),
]

def aplicar_alias_termo(nome: str) -> str:
    import re
    n = nome
    for padrao, forma in ALIAS_TERMO:
        n = re.sub(padrao, forma, n, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', n).strip()


def limpar_nome_promocional(nome: str) -> str:
    """
    Remove do nome do produto termos e slogans promocionais como:
    "Leve mais e pague menos", "Leve X pague Y", etc., e canoniciza meta-termos.
    Também expande apelidos do varejo (C/ -> com) e solta tamanho grudado (170g -> 170 g).
    """
    import re
    n = nome.strip()
    # 1. Remove "leve mais e pague menos" / "leve mais pague menos"
    n = re.sub(r'\s*\b(leve\s+mais\s+(e\s+)?pague\s+menos)\b\.?\s*$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\s*\b(leve\s+mais\s+(e\s+)?pague\s+menos)\b\.?\s*', '', n, flags=re.IGNORECASE)
    # 2. Remove "leve X pague Y" (ex: leve 3 pague 2, leve 4 pague 3)
    n = re.sub(r'\s*\b(leve\s+\d+\s+pague\s+\d+)\b\.?\s*$', '', n, flags=re.IGNORECASE)
    # 3. Remove "pague X leve Y" (ex: pague 2 leve 3)
    n = re.sub(r'\s*\b(pague\s+\d+\s+leve\s+\d+)\b\.?\s*$', '', n, flags=re.IGNORECASE)
    
    # 4. Canoniciza variações semânticas de termos promocionais coletivos
    n = canonicizar_meta_termos(n)

    # 5. Expande apelidos do varejo (C/ -> com sal, S/ -> sem, ...)
    n = aplicar_alias_termo(n)

    # 6. Solta tamanho grudado no nome ("170g" -> "170 g") para IDs consistentes
    # entre as duas grafias. (Visão com/sem tamanho se resolve na fusão
    # inteligente, que trata lado sem número à parte.)
    n = re.sub(r'(\d)\s*(kg|kilo|quilo|g|gr|gramas|ml|l|litro|litros)\b', r'\1 \2', n, flags=re.IGNORECASE)

    return re.sub(r'\s+', ' ', n).strip()

def normalizar_nome(nome: str, unidade: str = "") -> str:
    """
    Gera um ID único e legível para um produto.
    Ex: "Arroz Agulhinha Tio Urbano", "5kg" → "arroz-agulhinha-tio-urbano-5kg"
    """
    # Remove slogans promocionais e canoniciza meta-termos
    n = limpar_nome_promocional(nome)
    
    # Limpa sufixos redundantes de unidade do final do nome antes de normalizar
    n = re.sub(r'\s*\b(kg|kilo|quilo|un|und|unid|unidade|cada|g|gr|gramas|ml|l|litro|litros)\b\.?\s*$', '', n, flags=re.IGNORECASE)
    
    unidade_norm = normalizar_unidade(unidade)
    texto = f"{n} {unidade_norm}".strip().lower()
    texto = re.sub(r'[áàãâä]', 'a', texto)
    texto = re.sub(r'[éèêë]', 'e', texto)
    texto = re.sub(r'[íìîï]', 'i', texto)
    texto = re.sub(r'[óòõôö]', 'o', texto)
    texto = re.sub(r'[úùûü]', 'u', texto)
    texto = re.sub(r'[ç]', 'c', texto)
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    texto = re.sub(r'\s+', '-', texto.strip())
    return texto


def baixar_e_otimizar_imagem(url: str, produto_id: str) -> str:
    """
    Baixa uma imagem da URL, redimensiona para 200x200 pixels,
    compacta em JPEG com 75% de qualidade e faz o upload para o Firebase Storage.
    Retorna a URL pública da imagem hospedada.
    """
    if not url or not url.startswith("http"):
        return ""
        
    try:
        # 1. Download da imagem original
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        resp = session.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"❌ Erro ao baixar imagem da URL: {url} (Status {resp.status_code})")
            return ""
            
        # 2. Processamento com Pillow em memória
        img_bytes = io.BytesIO(resp.content)
        with Image.open(img_bytes) as img:
            # Converter para RGB se necessário (ex: PNG com canal alfa)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            # Redimensionamento para 200x200 px com filtro de alta qualidade
            img_redimensionada = img.resize((200, 200), Image.Resampling.LANCZOS)
            
            # Salvar em buffer de bytes na memória
            output_buffer = io.BytesIO()
            img_redimensionada.save(output_buffer, "JPEG", quality=75)
            output_buffer.seek(0)
            
            # 3. Enviar para o Firebase Storage
            bucket = storage.bucket("veja-o-preco.firebasestorage.app")
            blob_name = f"produtos/{produto_id}.jpg"
            blob = bucket.blob(blob_name)
            
            blob.upload_from_string(
                output_buffer.getvalue(),
                content_type="image/jpeg"
            )
            
            # Tornar a imagem pública para download
            blob.make_public()
            public_url = blob.public_url
            
            tamanho_kb = len(output_buffer.getvalue()) / 1024
            print(f"✅ Imagem otimizada e carregada no Storage: {public_url} ({tamanho_kb:.2f} KB)")
            
            # Opcional: Salvar também uma cópia local para auditoria em desenvolvimento
            try:
                base_dir = "/Users/jplima/Documents/veja-o-preco-backend"
                target_dir = os.path.join(base_dir, "auditoria_visual", "imagens_otimizadas")
                os.makedirs(target_dir, exist_ok=True)
                target_path = os.path.join(target_dir, f"{produto_id}.jpg")
                with open(target_path, "wb") as f_local:
                    f_local.write(output_buffer.getvalue())
            except Exception:
                pass
                
            return public_url
            
    except Exception as e:
        print(f"❌ Erro ao otimizar e fazer upload da imagem: {e}")
        return ""


def upload_imagem_cortada(img_bytes_original: bytes, box_2d: list, produto_id: str, nome_produto: str = "", unidade: str = "", marca: str = "", imagem_validada: bool = False) -> str:
    """
    Recorta uma imagem original com base no box_2d [ymin, xmin, ymax, xmax] normalizado (0 a 1000),
    redimensiona para 200x200 pixels, compacta em JPEG 75% e faz o upload para o Firebase Storage.
    Retorna a URL pública.
    """
    if not img_bytes_original or not box_2d or len(box_2d) != 4:
        return ""
        
    try:
        # O recorte acontece antes de salvar_produto_e_oferta() verificar o
        # cadastro. Sem esta guarda, um produto já curado era sobrescrito aqui
        # no mesmo caminho do Storage, mesmo que o UPSERT depois preservasse a
        # URL registrada no Firestore.
        db_conn = get_db()
        produto_id = resolver_produto_id_com_sinonimo(db_conn, produto_id, nome_produto, unidade, marca)
        produto_existente = db_conn.collection("produtos").document(produto_id).get()
        if produto_existente.exists:
            imagem_cadastrada = (produto_existente.to_dict() or {}).get("imagem_url", "")
            if imagem_cadastrada:
                print(f"🛡️ Imagem existente preservada para {produto_id}; recorte ignorado.")
                return imagem_cadastrada

        # A caixa de recorte vem da mesma extração que interpreta o encarte.
        # Sem uma segunda checagem do rótulo, título, marca, variante e peso,
        # não é evidência independente suficiente para publicar a imagem.
        if not imagem_validada:
            print(f"🛑 Recorte de {produto_id} retido: falta validação independente da embalagem.")
            return ""

        # 1. Processamento com Pillow
        img_bytes = io.BytesIO(img_bytes_original)
        with Image.open(img_bytes) as img:
            # Converter para RGB se necessário
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            width, height = img.size
            
            # Mapear coordenadas normalizadas (0 a 1000) para pixels
            ymin, xmin, ymax, xmax = box_2d
            left = (xmin / 1000.0) * width
            top = (ymin / 1000.0) * height
            right = (xmax / 1000.0) * width
            bottom = (ymax / 1000.0) * height
            
            # Garantir limites válidos e tamanho mínimo
            left = max(0.0, min(left, width))
            top = max(0.0, min(top, height))
            right = max(left + 1, min(right, width))
            bottom = max(top + 1, min(bottom, height))
            
            # Fazer o corte (crop)
            img_cortada = img.crop((left, top, right, bottom))
            
            # Redimensionamento para 200x200 px preservando proporção com fundo branco
            from PIL import ImageOps
            img_redimensionada = ImageOps.pad(img_cortada, (200, 200), color="white", centering=(0.5, 0.5))
            
            # Salvar em buffer
            output_buffer = io.BytesIO()
            img_redimensionada.save(output_buffer, "JPEG", quality=75)
            output_buffer.seek(0)
            
            # 2. Upload para Storage
            bucket = storage.bucket("veja-o-preco.firebasestorage.app")
            blob_name = f"produtos/{produto_id}.jpg"
            blob = bucket.blob(blob_name)
            
            try:
                # Cria apenas quando ainda não há imagem canônica. A condição
                # atômica também protege contra duas extrações concorrentes.
                blob.upload_from_string(
                    output_buffer.getvalue(),
                    content_type="image/jpeg",
                    if_generation_match=0
                )
            except Exception as upload_error:
                if getattr(upload_error, "code", None) == 412:
                    blob.reload()
                    print(f"🛡️ Imagem existente no Storage preservada para {produto_id}.")
                    return blob.public_url
                raise
            blob.make_public()
            public_url = blob.public_url
            
            tamanho_kb = len(output_buffer.getvalue()) / 1024.0
            print(f"✂️ Imagem recortada, otimizada e carregada no Storage: {public_url} ({tamanho_kb:.2f} KB)")
            
            # Copiar localmente para auditoria (seguindo o padrão do baixar_e_otimizar_imagem)
            try:
                base_dir = "/Users/jplima/Documents/veja-o-preco-backend"
                target_dir = os.path.join(base_dir, "auditoria_visual", "imagens_otimizadas")
                os.makedirs(target_dir, exist_ok=True)
                target_path = os.path.join(target_dir, f"{produto_id}.jpg")
                with open(target_path, "wb") as f_local:
                    f_local.write(output_buffer.getvalue())
            except Exception:
                pass
                
            return public_url
    except Exception as e:
        print(f"❌ Erro ao recortar/otimizar imagem do produto {produto_id}: {e}")
        return ""


def buscar_imagem(nome_produto: str, imagem_api: str = "") -> str:
    """
    Retorna somente a imagem explicitamente associada ao item pela fonte da loja.

    Busca genérica por nome em bases abertas (por exemplo, Open Food Facts) pode
    retornar marca, variante ou peso diferentes. Essas fontes não são vinculadas
    automaticamente ao cadastro; uma candidata precisa passar por validação
    independente antes de entrar no catálogo.
    """
    if isinstance(imagem_api, str) and imagem_api.startswith(("http://", "https://")):
        return imagem_api
    return ""


_CATALOGO_SIMILARIDADE_CACHE = []
_CATALOGO_SIMILARIDADE_ATUALIZADO = 0.0
_CATALOGO_SIMILARIDADE_TTL_SEGUNDOS = 300
_CATALOGO_SIMILARIDADE_LOCK = threading.Lock()
_SIMILARIDADE_SINONIMO_MINIMA = 0.90
_SIMILARIDADE_SINONIMO_MARGEM = 0.04
_MARCAS_COMUNS_PRODUTO = {
    "sadia", "seara", "perdigao", "nestle", "itambe", "italac", "piracanjuba",
    "bauducco", "marilan", "mabel", "parati", "vitarella", "estrela", "quero",
    "heinz", "hellmanns", "ype", "omo", "melitta", "pilao", "dona benta",
    "arisco", "fugini", "renata", "barilla", "catupiry", "danone", "garoto",
    "lacta", "quaker", "nescau", "toddy", "gomes da costa", "santa clara",
    "colgate", "sorriso", "nivea", "dove", "rexona", "pedigree", "whiskas",
    "frigol", "frimesa", "canção", "cancao", "yoki", "kitano", "knorr",
    "tio joao", "urbano",
}

_VARIANTES_CRITICAS = {
    "adulto", "adultos", "filhote", "filhotes", "senior", "junior",
    "integral", "desnatado", "desnatada", "semidesnatado", "semidesnatada",
    "zero", "light", "diet", "tradicional", "premium", "gourmet", "classico", "original",
    "congelado", "congelada", "resfriado", "resfriada", "defumado", "defumada", "picante", "suave",
    "morango", "uva", "chocolate", "laranja", "limao", "abacaxi", "manga", "maracuja", "pessego", "coco", "baunilha", "natural",
    "frango", "bovino", "bovina", "suino", "suina", "peru", "peixe", "patinho", "alcatra", "figado", "coracao", "musculo", "acem", "mocoto", "costela", "paleta", "panceta", "pernil", "peito", "coxa", "sobrecoxa", "asa", "file", "pescada", "piramutaba", "tambaqui", "tilapia",
    "com", "sem", "pele", "osso", "desossado", "desossada", "fatiado", "fatiada",
    "moido", "moida", "inteiro", "inteira", "po", "liquido", "liquida",
}


def _normalizar_texto_similaridade(texto: str) -> str:
    texto = canonicizar_meta_termos(limpar_nome_promocional(texto or ""))
    texto = aplicar_alias_termo(texto)
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    # Unifica grafias de quantidade (1 L = 1000 ml; 1kg = 1000 g) no score.
    def medida(match):
        valor = float(match.group(1).replace(",", "."))
        unidade = match.group(2)
        if unidade in {"kg", "quilo", "quilos"}:
            valor, unidade = valor * 1000, "g"
        elif unidade in {"g", "gr", "gramas"}:
            unidade = "g"
        elif unidade in {"l", "litro", "litros"}:
            valor, unidade = valor * 1000, "ml"
        elif unidade in {"ml", "mililitros"}:
            unidade = "ml"
        return f"medida{valor:g}{unidade}"
    texto = re.sub(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(kg|quilo|quilos|g|gr|gramas|ml|mililitros|l|litro|litros)\b", medida, texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    # Recipientes/unidades de venda variam entre encartes e não identificam a variante.
    texto = re.sub(r"\b(pacote|embalagem|unidade|unid|und|cada|pote|lata|caixa|fardo|display)\b", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _extrair_quantidades_produto(texto: str) -> tuple:
    """Extrai pesos/volumes para impedir que tamanhos diferentes sejam fundidos."""
    normalizado = unicodedata.normalize("NFKD", (texto or "").lower())
    normalizado = "".join(c for c in normalizado if not unicodedata.combining(c))
    normalizado = re.sub(r"\s+", " ", normalizado)
    encontrados = re.findall(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*(kg|quilo|quilos|g|gr|gramas|ml|mililitros|l|litro|litros)\b", normalizado)
    quantidades = []
    for numero, unidade in encontrados:
        valor = float(numero.replace(",", "."))
        if unidade in {"kg", "quilo", "quilos"}:
            quantidades.append(("g", round(valor * 1000, 3)))
        elif unidade in {"g", "gr", "gramas"}:
            quantidades.append(("g", round(valor, 3)))
        elif unidade in {"l", "litro", "litros"}:
            quantidades.append(("ml", round(valor * 1000, 3)))
        else:
            quantidades.append(("ml", round(valor, 3)))
    # Mantém multiplicadores de fardos/caixas (ex.: 12x350ml), além do volume.
    multiplicadores = re.findall(r"\b(\d+)\s*x\s*(?=\d)", normalizado)
    return tuple(sorted(quantidades)), tuple(sorted(int(x) for x in multiplicadores))


def _pontuar_similaridade_produtos(nome_a: str, nome_b: str) -> float:
    a = _normalizar_texto_similaridade(nome_a)
    b = _normalizar_texto_similaridade(nome_b)
    if not a or not b:
        return 0.0
    direta = difflib.SequenceMatcher(None, a, b).ratio()
    tokens_a, tokens_b = set(a.split()), set(b.split())
    ordenada_a, ordenada_b = " ".join(sorted(tokens_a)), " ".join(sorted(tokens_b))
    por_tokens = difflib.SequenceMatcher(None, ordenada_a, ordenada_b).ratio()
    overlap = len(tokens_a & tokens_b) / max(1, min(len(tokens_a), len(tokens_b)))
    return (0.50 * por_tokens) + (0.25 * direta) + (0.25 * overlap)


def _variantes_incompativeis(nome_a: str, nome_b: str) -> bool:
    a = set(_normalizar_texto_similaridade(nome_a).split())
    b = set(_normalizar_texto_similaridade(nome_b).split())
    return bool((a ^ b) & _VARIANTES_CRITICAS)


def _marca_detectada(nome: str, marca: str = "") -> str:
    if marca:
        return _normalizar_texto_similaridade(marca)
    normalizado = _normalizar_texto_similaridade(nome)
    encontradas = []
    for marca_conhecida in _MARCAS_COMUNS_PRODUTO:
        achado = re.search(rf"\b{re.escape(marca_conhecida)}\b", normalizado)
        if achado:
            encontradas.append((achado.start(), -len(marca_conhecida), marca_conhecida))
    return sorted(encontradas)[0][2] if encontradas else ""


def _carregar_catalogo_similaridade(db_conn) -> list:
    """Carrega o catálogo uma vez por instância, evitando uma leitura por item."""
    global _CATALOGO_SIMILARIDADE_CACHE, _CATALOGO_SIMILARIDADE_ATUALIZADO
    agora = time.monotonic()
    if agora - _CATALOGO_SIMILARIDADE_ATUALIZADO < _CATALOGO_SIMILARIDADE_TTL_SEGUNDOS:
        return _CATALOGO_SIMILARIDADE_CACHE
    with _CATALOGO_SIMILARIDADE_LOCK:
        agora = time.monotonic()
        if agora - _CATALOGO_SIMILARIDADE_ATUALIZADO < _CATALOGO_SIMILARIDADE_TTL_SEGUNDOS:
            return _CATALOGO_SIMILARIDADE_CACHE
        catalogo = []
        for doc in db_conn.collection("produtos").stream():
            dados = doc.to_dict() or {}
            catalogo.append({"id": doc.id, **dados})
        _CATALOGO_SIMILARIDADE_CACHE = catalogo
        _CATALOGO_SIMILARIDADE_ATUALIZADO = time.monotonic()
        return _CATALOGO_SIMILARIDADE_CACHE


def _registrar_produto_cache_similaridade(produto_id: str, dados: dict):
    """Mantém o índice morno coerente com produtos criados por esta instância."""
    if time.monotonic() - _CATALOGO_SIMILARIDADE_ATUALIZADO >= _CATALOGO_SIMILARIDADE_TTL_SEGUNDOS:
        return
    with _CATALOGO_SIMILARIDADE_LOCK:
        if not any(p.get("id") == produto_id for p in _CATALOGO_SIMILARIDADE_CACHE):
            _CATALOGO_SIMILARIDADE_CACHE.append({"id": produto_id, **dados})


def _buscar_sinonimo_aproximado(db_conn, produto_id: str, nome_produto: str = "", unidade: str = "", marca: str = "") -> str:
    nome_origem = nome_produto or produto_id.replace("-", " ")
    qtd_origem = _extrair_quantidades_produto(nome_origem)
    unidade_origem = normalizar_unidade(unidade) if unidade else ""
    candidatos = []
    for produto in _carregar_catalogo_similaridade(db_conn):
        candidato_id = produto.get("id", "")
        if not candidato_id or candidato_id == produto_id:
            continue
        nome_candidato = produto.get("nome") or candidato_id.replace("-", " ")
        unidade_candidata = normalizar_unidade(produto.get("unidade", ""))
        if unidade_origem and unidade_candidata and unidade_origem != unidade_candidata:
            continue
        if _variantes_incompativeis(nome_origem, nome_candidato):
            continue
        marca_origem = _marca_detectada(nome_origem, marca)
        marca_candidata = _marca_detectada(nome_candidato, produto.get("marca", ""))
        if marca_origem and marca_candidata and marca_origem != marca_candidata:
            continue
        qtd_candidata = _extrair_quantidades_produto(nome_candidato)
        if qtd_origem != ((), ()) and qtd_candidata != ((), ()) and qtd_origem != qtd_candidata:
            continue
        # Se só um nome informa o tamanho, não cria alias automaticamente.
        if (qtd_origem == ((), ())) != (qtd_candidata == ((), ())):
            continue
        score = _pontuar_similaridade_produtos(nome_origem, nome_candidato)
        if score >= _SIMILARIDADE_SINONIMO_MINIMA:
            candidatos.append((score, candidato_id, nome_candidato))
    candidatos.sort(reverse=True)
    if not candidatos:
        return ""
    melhor_score, melhor_id, melhor_nome = candidatos[0]
    segundo_score = candidatos[1][0] if len(candidatos) > 1 else 0.0
    if segundo_score and melhor_score - segundo_score < _SIMILARIDADE_SINONIMO_MARGEM:
        print(f"  🔎 Nome ambíguo ({melhor_score:.0%} vs {segundo_score:.0%}); mantido para revisão: {nome_origem}")
        return ""
    ref_sinonimo = db_conn.collection("sinonimos").document(produto_id)
    try:
        ref_sinonimo.create({
            "id_correto": melhor_id,
            "criado_em": firestore.SERVER_TIMESTAMP,
            "metodo": "similaridade_catalogo",
            "similaridade_pct": round(melhor_score * 100, 1),
            "nome_origem": nome_origem,
            "nome_canonico": melhor_nome,
        })
        print(f"  🧠 Sinônimo automático ({melhor_score:.1%}): '{nome_origem}' → '{melhor_nome}' [{melhor_id}]")
        return melhor_id
    except Exception as erro:
        # Outra extração pode ter criado o alias primeiro. Respeita o redirecionamento vencedor.
        try:
            alias_existente = ref_sinonimo.get()
            destino = (alias_existente.to_dict() or {}).get("id_correto") if alias_existente.exists else ""
            if destino:
                return destino
        except Exception:
            pass
        print(f"  ⚠️ Não foi possível registrar sinônimo aproximado para '{nome_origem}': {erro}")
        return ""


def resolver_produto_id_com_sinonimo(db_conn, produto_id: str, nome_produto: str = "", unidade: str = "", marca: str = "") -> str:
    """
    Verifica se o produto_id possui um redirecionamento cadastrado na coleção 'sinonimos'.
    Retorna o id_correto se existir, ou o próprio produto_id original.
    Suporta resolução em cadeia (ex: A -> B -> C).
    """
    id_atual = produto_id
    iteracoes = 0
    try:
        while iteracoes < 5:
            ref_sinonimo = db_conn.collection("sinonimos").document(id_atual).get()
            if ref_sinonimo.exists:
                id_correto = ref_sinonimo.to_dict().get("id_correto")
                if id_correto and id_correto != id_atual:
                    print(f"  🔄 Redirecionando produto_id '{id_atual}' para o sinônimo '{id_correto}'")
                    id_atual = id_correto
                    iteracoes += 1
                else:
                    break
            else:
                break
        # IDs ainda não cadastrados podem ser ligados a um produto conhecido
        # quando a similaridade é alta, tamanho/unidade batem e não há variação incompatível.
        if id_atual == produto_id:
            doc_produto = db_conn.collection("produtos").document(produto_id).get()
            if not doc_produto.exists:
                id_aproximado = _buscar_sinonimo_aproximado(db_conn, produto_id, nome_produto, unidade, marca)
                if id_aproximado:
                    id_atual = id_aproximado
                    while iteracoes < 5:
                        ref_sinonimo = db_conn.collection("sinonimos").document(id_atual).get()
                        if not ref_sinonimo.exists:
                            break
                        destino = (ref_sinonimo.to_dict() or {}).get("id_correto")
                        if not destino or destino == id_atual:
                            break
                        id_atual = destino
                        iteracoes += 1
    except Exception as e:
        print(f"⚠️ Erro ao buscar sinônimo para '{produto_id}': {e}")
    return id_atual


# Mapa de cadeias: lojas da mesma rede cujas ofertas formam um banco unido.
# A comparação entre queries consulta as lojas irmãs antes de criar documento
# novo (mesmo produto+preço válido na irmã -> reaproveita e carimba a loja).
# Começa fixo e mínimo (MVP); vira cadastro quando as redes expandirem.
CADEIAS = {
    "mateus": ["mateus_site", "mateus-jaderlandia"],
}

def lojas_irmas(supermercado_id: str) -> list:
    for _, lojas in CADEIAS.items():
        if supermercado_id in lojas:
            return [l for l in lojas if l != supermercado_id]
    return []


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
    post_id: str = None,
    imagem_origem: str = ""
) -> dict:
    """
    Realiza o UPSERT do produto e registra a oferta no Firestore.
    - Se o produto não existe → cria em /produtos e busca imagem
    - Se já existe → apenas atualiza o timestamp
    - Sempre cria uma nova oferta em /ofertas com TTL de 7 dias
    """
    db = firestore.client()
    nome = limpar_nome_promocional(nome)
    unidade_norm = normalizar_unidade(unidade)
    produto_id = normalizar_nome(nome, unidade_norm)
    produto_id = resolver_produto_id_com_sinonimo(db, produto_id, nome, unidade_norm, marca)

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

    categoria = normalizar_categoria(categoria, nome)

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

    imagem_url = ""
    if not doc_produto.exists:
        imagem_original = buscar_imagem(nome, imagem_api)
        if imagem_original:
            if any(host in imagem_original for host in ["firebasestorage.googleapis.com", "storage.googleapis.com"]):
                imagem_url = imagem_original
            else:
                imagem_url = baixar_e_otimizar_imagem(imagem_original, produto_id)
                if not imagem_url:
                    imagem_url = imagem_original
        
        # Determina a origem final
        origem_final = imagem_origem
        if not origem_final:
            if imagem_url:
                if imagem_original == imagem_api:
                    origem_final = "api_loja"
                else:
                    origem_final = "open_food_facts"
            else:
                origem_final = "padrao"

        ref_produto.set({
            "nome": nome,
            "marca": marca,
            "unidade": unidade_norm,
            "categoria": categoria,
            "imagem_url": imagem_url,
            "imagem_origem": origem_final,
            "supermercado_origem": supermercado_id,
            "criado_em": datetime.now(),
            "atualizado_em": datetime.now()
        })
        _registrar_produto_cache_similaridade(produto_id, {
            "nome": nome, "marca": marca, "unidade": unidade_norm,
            "categoria": categoria, "imagem_url": imagem_url,
            "imagem_origem": origem_final,
        })
    else:
        dados_produto = doc_produto.to_dict()
        imagem_url = dados_produto.get("imagem_url", "")
        
        # Radar de Repetição / Caching no Storage / Bypass
        # Se a imagem cadastrada for externa, tenta otimizar agora e salvar no Storage
        if imagem_url and not any(host in imagem_url for host in ["firebasestorage.googleapis.com", "storage.googleapis.com"]):
            imagem_otimizada = baixar_e_otimizar_imagem(imagem_url, produto_id)
            if imagem_otimizada:
                imagem_url = imagem_otimizada
                origem_final = dados_produto.get("imagem_origem") or "open_food_facts"
                ref_produto.update({
                    "imagem_url": imagem_url,
                    "imagem_origem": origem_final,
                    "atualizado_em": datetime.now()
                })
        elif not imagem_url:
            imagem_original = buscar_imagem(nome, imagem_api)
            if imagem_original:
                imagem_otimizada = baixar_e_otimizar_imagem(imagem_original, produto_id)
                imagem_url = imagem_otimizada if imagem_otimizada else imagem_original
                
                origem_final = imagem_origem
                if not origem_final:
                    if imagem_original == imagem_api:
                        origem_final = "api_loja"
                    else:
                        origem_final = "open_food_facts"

                ref_produto.update({
                    "imagem_url": imagem_url,
                    "imagem_origem": origem_final,
                    "atualizado_em": datetime.now()
                })
        else:
            # Bypass Total (Já é uma imagem no Storage)
            # Para retrocompatibilidade: se o produto antigo não tiver imagem_origem, setamos como "manual" para proteger
            if "imagem_origem" not in dados_produto:
                ref_produto.update({
                    "imagem_origem": "manual",
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
    # Um único produto/loja só deve ter um preço vigente. Expira preços
    # anteriores antes do retorno por duplicata, e recolhe todas as cópias
    # exatas em vez de atualizar apenas a primeira encontrada.
    agora_dedupe = datetime.now()
    ofertas_mesmo_produto = get_db().collection("ofertas").where(
        "produto_id", "==", produto_id
    ).stream()
    ofertas_mesma_chave = []
    for doc_oferta in ofertas_mesmo_produto:
        dados_oferta = doc_oferta.to_dict() or {}
        if dados_oferta.get("supermercado_id") != supermercado_id:
            continue
        expiracao = dados_oferta.get("expira_em")
        if not expiracao:
            continue
        if getattr(expiracao, "tzinfo", None) is not None:
            expiracao = expiracao.replace(tzinfo=None)
        if expiracao < agora_dedupe:
            continue
        if dados_oferta.get("preco") == preco:
            ofertas_mesma_chave.append((doc_oferta, dados_oferta))
        else:
            doc_oferta.reference.update({"expira_em": agora_dedupe - timedelta(seconds=1)})
            print(f"  ♻️ Preço anterior expirado antes do upsert: {nome}")
    
    # --- Registro Permanente em /historico_precos (Idempotente: 1 cotação por dia por produto/loja) ---
    data_hoje_str = datetime.now().strftime("%Y-%m-%d")
    historico_id = f"{produto_id}_{supermercado_id}_{data_hoje_str}"
    try:
        get_db().collection("historico_precos").document(historico_id).set({
            "produto_id": produto_id,
            "produto_nome": nome,
            "supermercado_id": supermercado_id,
            "loja": loja,
            "preco": preco,
            "preco_antigo": preco_antigo,
            "unidade": unidade_norm,
            "categoria": categoria,
            "data": data_hoje_str,
            "imagem_url": imagem_url,
            "criado_em": datetime.now()
        }, merge=True)
    except Exception as e_hist:
        print(f"  ⚠️ Aviso: Falha não-bloqueante ao registrar historico_precos: {e_hist}")

    if ofertas_mesma_chave:
        # Mantém o documento mais recente e junta referências antes de apagar
        # cópias com a mesma chave exata produto+loja+preço.
        ofertas_mesma_chave.sort(
            key=lambda par: (par[1].get("criado_em").timestamp()
                             if hasattr(par[1].get("criado_em"), "timestamp") else 0),
            reverse=True
        )
        doc_duplicado, dados_duplicado = ofertas_mesma_chave[0]
        lojas_ids = {supermercado_id}
        ids_canonicos = dados_duplicado.get("supermercado_ids") or []
        if isinstance(ids_canonicos, str):
            ids_canonicos = [ids_canonicos]
        lojas_ids.update(id_loja for id_loja in ids_canonicos if isinstance(id_loja, str) and id_loja)
        for _, dados_copia in ofertas_mesma_chave[1:]:
            ids_copia = dados_copia.get("supermercado_ids") or []
            if isinstance(ids_copia, str):
                ids_copia = [ids_copia]
            lojas_ids.update(id_loja for id_loja in ids_copia if isinstance(id_loja, str) and id_loja)
        atualizacao = {
            "expira_em": agora_dedupe + timedelta(days=7),
            "produto_nome": nome,
            "supermercado_ids": sorted(lojas_ids),
        }
        if imagem_url:
            atualizacao["imagem_url"] = imagem_url
        if post_id and not dados_duplicado.get("post_id"):
            atualizacao["post_id"] = post_id
            print(f"  📝 Post ID atualizado para oferta existente: {nome}")
        elif not dados_duplicado.get("post_id"):
            post_id_existente = next((d.get("post_id") for _, d in ofertas_mesma_chave[1:] if d.get("post_id")), None)
            if post_id_existente:
                atualizacao["post_id"] = post_id_existente
        for campo in ("validade", "preco_antigo", "loja"):
            if not dados_duplicado.get(campo):
                valor_existente = next((d.get(campo) for _, d in ofertas_mesma_chave[1:] if d.get(campo)), None)
                if valor_existente is not None:
                    atualizacao[campo] = valor_existente
        doc_duplicado.reference.update(atualizacao)
        for doc_copia, _ in ofertas_mesma_chave[1:]:
            doc_copia.reference.delete()
        if len(ofertas_mesma_chave) > 1:
            print(f"  🧹 {len(ofertas_mesma_chave) - 1} oferta(s) duplicada(s) exata(s) removida(s): {nome}")
        
        print(f"  ⏭️ Oferta recusada pelo Banco (já existe e ainda é válida): {nome} a R$ {preco}")
        return {"produto_id": produto_id, "salvo": True, "duplicado": True}

    # --- Comparação entre queries (banco unido): mesmo produto+preço válido
    # em loja irmã da mesma cadeia -> reaproveita o documento (carimba a loja
    # e renova a validade) em vez de criar duplicata entre queries.
    try:
        agora_reuso = datetime.now()
        for sid_irma in lojas_irmas(supermercado_id):
            q_irma = get_db().collection("ofertas").where(
                "produto_id", "==", produto_id
            ).where(
                "supermercado_id", "==", sid_irma
            ).where(
                "preco", "==", preco
            ).stream()
            for d_irma in q_irma:
                vd = d_irma.to_dict()
                exp = vd.get("expira_em")
                if not exp:
                    continue
                if getattr(exp, "tzinfo", None) is not None:
                    exp = exp.replace(tzinfo=None)
                if exp < agora_reuso:
                    continue
                lojas_ids = vd.get("supermercado_ids") or [vd.get("supermercado_id")]
                if supermercado_id not in lojas_ids:
                    lojas_ids = lojas_ids + [supermercado_id]
                upd = {
                    "supermercado_ids": lojas_ids,
                    "expira_em": agora_reuso + timedelta(days=7),
                    "produto_nome": nome,
                }
                if imagem_url:
                    upd["imagem_url"] = imagem_url
                d_irma.reference.update(upd)
                print(f"  🔗 Oferta reaproveitada entre queries ({sid_irma} + {supermercado_id}): {nome}")
                return {"produto_id": produto_id, "salvo": True, "duplicado": True, "reuso_entre_queries": True}
    except Exception as e_reuso:
        print(f"  ⚠️ Aviso: falha na comparação entre queries: {e_reuso}")

    # IDs determinísticos tornam a gravação idempotente caso duas extrações
    # processem a mesma oferta no mesmo dia ao mesmo tempo.
    data_oferta_id = datetime.now().strftime("%Y-%m-%d")
    ref_nova_oferta = get_db().collection("ofertas").document(
        f"{supermercado_id}_{produto_id}_{data_oferta_id}"
    )
    ref_nova_oferta.set({
        "produto_id": produto_id,
        "produto_nome": nome,
        "supermercado_id": supermercado_id,
        "supermercado_ids": [supermercado_id],
        "loja": loja,
        "preco": preco,
        "preco_antigo": preco_antigo,
        "unidade": unidade_norm,
        "categoria": categoria,
        "metodo": metodo,
        "validade": validade,
        "post_id": post_id,
        "expira_em": expira_em,
        "imagem_url": imagem_url,
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
                "imagem_url": oferta.get("imagem_url", ""),
            })

        headers = {
            "Cache-Control": "public, max-age=600"
        }

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
            mimetype="application/json",
            headers=headers
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

@https_fn.on_request()
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
        imagens_bytes = []
        for url in imagens_encarte:
            img_data = session.get(url).content
            imagens_bytes.append(img_data)
            gemini_parts.append(types.Part.from_bytes(data=img_data, mime_type="image/jpeg"))

        prompt = """
        Analise o encarte do Assaí Atacadista e extraia os produtos de supermercado.
        FOCO: Alimentos, Higiene, Limpeza e Bebidas Não-Alcoólicas.
        IGNORE: Bebidas Alcoólicas (Cerveja, Vinho, etc.) e itens de Bazar (Eletrônicos, Eletro, Moda).
        
        REGRAS ADICIONAIS:
        - Para cada produto extraído, identifique as coordenadas da foto do produto (o pacote, garrafa ou item físico propriamente dito, excluindo o preço ou outras decorações) e retorne como "box_2d" no formato [ymin, xmin, ymax, xmax] normalizado de 0 a 1000. Seja o mais restrito e justo possível à embalagem/produto em si.
        - Informe no campo "quadro_index" o índice (base 0) da imagem/página do encarte onde o produto foi identificado e de onde o box_2d foi calculado.
        
        Retorne APENAS o JSON puro no formato:
        {
            "itens": [
                {
                    "produto": "NOME",
                    "preco": 0.0,
                    "unidade": "un",
                    "categoria": "CATEGORIA",
                    "box_2d": [ymin, xmin, ymax, xmax],
                    "quadro_index": 0
                }
            ]
        }
        """
        gemini_parts.append(prompt)

        response_gemini = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=gemini_parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # 4. Parse e Salvar no Firestore
        try:
            texto_limpo = response_gemini.text.replace("```json", "").replace("```", "").strip()
            resultado = json.loads(texto_limpo)
            itens = resultado.get("itens", [])

            for item in itens:
                # --- RECORTE DE IMAGEM VIA IA ---
                img_bytes_original = None
                box_2d = item.get("box_2d")
                try:
                    quadro_index = int(item.get("quadro_index", 0))
                except Exception:
                    quadro_index = 0

                if box_2d and len(box_2d) == 4:
                    if 0 <= quadro_index < len(imagens_bytes):
                        img_bytes_original = imagens_bytes[quadro_index]

                imagem_url_crop = ""
                if img_bytes_original:
                    temp_prod_id = normalizar_nome(item.get("produto", ""), item.get("unidade", "un"))
                    imagem_url_crop = upload_imagem_cortada(
                        img_bytes_original, box_2d, temp_prod_id,
                        item.get("produto", ""), item.get("unidade", "un"), item.get("marca", "")
                    )

                salvar_produto_e_oferta(
                    nome=item["produto"],
                    preco=item["preco"],
                    unidade=item["unidade"],
                    categoria=item["categoria"],
                    supermercado_id="assai",
                    loja="Assaí Atacadista",
                    metodo="site_tabloide",
                    imagem_api=imagem_url_crop if imagem_url_crop else "",
                    imagem_origem="auto_crop" if imagem_url_crop else ""
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

@https_fn.on_request(timeout_sec=540, memory=options.MemoryOption.GB_1)
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
            
            # 4. Leitura do arquivo PDF para envio nativo ao Vertex AI
            print(f"DEBUG GEMINI - Lendo arquivo PDF para envio nativo: {tmp_path}")
            with open(tmp_path, "rb") as f_pdf:
                pdf_bytes = f_pdf.read()
            uploaded_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
            print("DEBUG GEMINI - Part do PDF criada com sucesso.")

            # 5. Roteamento e Prompt
            modelo_escolhido = "gemini-3.1-flash-lite"
            prompt_instrucao = """
            Você é um assistente de elite para extração de dados de encartes de supermercado.
            Sua missão é extrair TODOS os produtos e ofertas presentes no PDF anexado.
            
            FOCO PRINCIPAL: 
            Todos os itens de supermercado devem ser extraídos e classificados entre: ALIMENTOS, CARNES, HORTIFRUTI, PADARIA, BEBIDAS, HIGIENE, LIMPEZA, FRIOS_LATICINIOS, PET.
            
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
                        "categoria": "ALIMENTOS/CARNES/HORTIFRUTI/PADARIA/BEBIDAS/HIGIENE/LIMPEZA/FRIOS_LATICINIOS/PET",
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
                    contents=[uploaded_part, prompt_instrucao],
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
            reaproveitadas = 0

            db_conn = get_db()
            batch = db_conn.batch()
            produtos_cadastrados = {}

            # Filtro de categorias proibidas
            categorias_proibidas = ["BAZAR", "ELETRÔNICOS", "ELETRO", "MODA", "VESTUÁRIO", "AUTOMOTIVO", "BRINQUEDOS", "FERRAMENTAS", "MÓVEIS", "CASA"]

            # Antiduplicação: carrega ofertas válidas desta loja UMA vez (evita índice
            # composto: filtra expira_em em memória). Mesma regra de salvar_produto_e_oferta:
            # mesmo produto+loja+preço ainda válido -> atualiza em vez de criar novo doc.
            agora = datetime.now()
            vigentes = {}  # (produto_id, preco) -> (doc_ref, criado_em)
            referencias_duplicadas_vigentes = []
            try:
                for doc in db_conn.collection("ofertas").where(
                    "supermercado_id", "==", supermercado_id
                ).stream():
                    v = doc.to_dict()
                    exp = v.get("expira_em")
                    if not exp:
                        continue
                    if getattr(exp, "tzinfo", None) is not None:
                        exp = exp.replace(tzinfo=None)
                    if exp >= agora:
                        if not v.get("produto_id") or v.get("preco") is None:
                            continue
                        chave = (v.get("produto_id"), v.get("preco"))
                        ant = vigentes.get(chave)
                        criado = v.get("criado_em")
                        timestamp_criado = criado.timestamp() if hasattr(criado, "timestamp") else 0
                        timestamp_anterior = ant[1].timestamp() if ant and hasattr(ant[1], "timestamp") else 0
                        if ant is None:
                            vigentes[chave] = (doc.reference, v.get("criado_em"))
                        elif timestamp_criado > timestamp_anterior:
                            referencias_duplicadas_vigentes.append(ant[0])
                            vigentes[chave] = (doc.reference, criado)
                        else:
                            referencias_duplicadas_vigentes.append(doc.reference)
            except Exception as e_vig:
                print(f"  ⚠️ Antiduplicação desativada nesta execução: {str(e_vig)[:80]}")
                vigentes = {}
                referencias_duplicadas_vigentes = []

            # Se o banco já tiver cópias ativas exatas (mesmo produto, loja e
            # preço), conserva a mais recente. A limpeza é limitada a essa
            # chave inequívoca; variações de nome/tamanho continuam para revisão.
            for inicio in range(0, len(referencias_duplicadas_vigentes), 400):
                lote_limpeza = db_conn.batch()
                for referencia in referencias_duplicadas_vigentes[inicio:inicio + 400]:
                    lote_limpeza.delete(referencia)
                lote_limpeza.commit()
            if referencias_duplicadas_vigentes:
                print(f"  🧹 Removidas {len(referencias_duplicadas_vigentes)} ofertas ativas duplicadas exatas de {supermercado_id}.")

            # Comparação entre queries: vigentes das lojas irmãs para reuso.
            vigentes_irmas = {}  # (produto_id, preco) -> (doc_ref, doc_dict)
            try:
                for sid_irma in lojas_irmas(supermercado_id):
                    for doc in db_conn.collection("ofertas").where(
                        "supermercado_id", "==", sid_irma
                    ).stream():
                        v = doc.to_dict()
                        exp = v.get("expira_em")
                        if not exp:
                            continue
                        if getattr(exp, "tzinfo", None) is not None:
                            exp = exp.replace(tzinfo=None)
                        if exp >= agora and v.get("preco") is not None:
                            chave = (v.get("produto_id"), v.get("preco"))
                            if chave not in vigentes_irmas:
                                vigentes_irmas[chave] = (doc.reference, v)
            except Exception as e_irma:
                print(f"  ⚠️ Comparação entre queries desativada: {str(e_irma)[:80]}")
                vigentes_irmas = {}

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
                    produto_id = resolver_produto_id_com_sinonimo(db_conn, produto_id, nome, unidade, item.get("marca", ""))
                    
                    # --- OPERAÇÃO BATCH ---
                    ref_prod = db_conn.collection("produtos").document(produto_id)
                    if produto_id not in produtos_cadastrados:
                        produto_existente = ref_prod.get()
                        dados_produto_existente = produto_existente.to_dict() if produto_existente.exists else {}
                        produtos_cadastrados[produto_id] = {
                            "imagem_url": (dados_produto_existente or {}).get("imagem_url", ""),
                            "nome": (dados_produto_existente or {}).get("nome", ""),
                            "unidade": (dados_produto_existente or {}).get("unidade", ""),
                            "categoria": (dados_produto_existente or {}).get("categoria", ""),
                            "existe": produto_existente.exists,
                        }
                    dados_produto = produtos_cadastrados[produto_id]
                    imagem_cadastrada = dados_produto["imagem_url"]
                    # Um rótulo variável do encarte não deve renomear o produto
                    # mestre que já foi curado; preenche só campos ausentes.
                    produto_nome = dados_produto["nome"] or nome
                    campos_produto = {"atualizado_em": datetime.now()}
                    if not dados_produto["nome"]:
                        campos_produto["nome"] = nome
                    if not dados_produto["unidade"]:
                        campos_produto["unidade"] = unidade
                    if not dados_produto["categoria"]:
                        campos_produto["categoria"] = categoria_item
                    batch.set(ref_prod, campos_produto, merge=True)
                    if not dados_produto["existe"]:
                        _registrar_produto_cache_similaridade(produto_id, {
                            "nome": produto_nome,
                            "unidade": unidade,
                            "categoria": categoria_item,
                            "imagem_url": imagem_cadastrada,
                        })

                    # Referência da Oferta
                    hoje_str = datetime.now().strftime("%Y-%m-%d")
                    oferta_id = f"{supermercado_id}_{produto_id}_{hoje_str}"
                    ref_oferta = db_conn.collection("ofertas").document(oferta_id)

                    # Antiduplicação: mesmo produto+loja+preço ainda válido -> atualiza
                    # a oferta existente (renova expiração) em vez de empilhar novo doc.
                    chave_vigente = (produto_id, preco)
                    # Encerra qualquer preço anterior do produto mesmo quando a
                    # oferta do preço atual já existe. Antes, esse caso dava
                    # continue no bloco abaixo e deixava os dois preços ativos.
                    chaves_antigas = [k for k in vigentes if k[0] == produto_id and k[1] != preco]
                    for k_ant in chaves_antigas:
                        ref_ant, _ = vigentes.pop(k_ant)
                        batch.set(ref_ant, {
                            "expira_em": datetime.now() - timedelta(seconds=1),
                        }, merge=True)

                    if chave_vigente in vigentes:
                        ref_existente, _ = vigentes[chave_vigente]
                        batch.set(ref_existente, {
                            "produto_nome": produto_nome,
                            "unidade": unidade,
                            "categoria": categoria_item,
                            "metodo": "gemini_pdf_batch",
                            "expira_em": datetime.now() + timedelta(days=7),
                            **({"imagem_url": imagem_cadastrada} if imagem_cadastrada else {}),
                        }, merge=True)
                        reaproveitadas += 1
                        salvos += 1
                        if salvos % 200 == 0:
                            batch.commit()
                            batch = db_conn.batch()
                        continue

                    # Comparação entre queries: já existe válido em loja irmã ->
                    # carimba a loja e renova, sem criar duplicata entre queries.
                    if chave_vigente in vigentes_irmas:
                        ref_irma, v_irma = vigentes_irmas[chave_vigente]
                        lojas_ids = v_irma.get("supermercado_ids") or [v_irma.get("supermercado_id")]
                        if supermercado_id not in lojas_ids:
                            lojas_ids = lojas_ids + [supermercado_id]
                        batch.set(ref_irma, {
                            "supermercado_ids": lojas_ids,
                            "produto_nome": produto_nome,
                            "expira_em": datetime.now() + timedelta(days=7),
                            **({"imagem_url": imagem_cadastrada} if imagem_cadastrada else {}),
                        }, merge=True)
                        reaproveitadas += 1
                        salvos += 1
                        if salvos % 200 == 0:
                            batch.commit()
                            batch = db_conn.batch()
                        continue

                    vigentes[chave_vigente] = (ref_oferta, datetime.now())

                    batch.set(ref_oferta, {
                        "produto_id": produto_id,
                        "produto_nome": produto_nome,
                        "supermercado_id": supermercado_id,
                        "supermercado_ids": [supermercado_id],
                        "loja": loja_nome,
                        "preco": preco,
                        "unidade": unidade,
                        "categoria": categoria_item,
                        "metodo": "gemini_pdf_batch",
                        "expira_em": datetime.now() + timedelta(days=7),
                        "criado_em": datetime.now(),
                        **({"imagem_url": imagem_cadastrada} if imagem_cadastrada else {}),
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
@https_fn.on_request(timeout_sec=540, memory=options.MemoryOption.GB_1)
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

            # 3. Preparar mídia para envio nativo ao Vertex AI
            tipo_nome = "vídeo" if is_video else "imagem"
            mime = "video/mp4" if is_video else (content_type or "image/jpeg")
            print(f"DEBUG VISION - Criando Part nativa do Vertex AI para {tipo_nome} ({mime})...")
            gemini_parts.append(types.Part.from_bytes(data=response.content, mime_type=mime))

        try:
            # 4. Prompt de Visão estruturado com Filtro de Categorias RÍGIDO
            prompt_vision = """
            Você é um assistente de visão computacional especializado em varejo de supermercado.
            Analise a imagem(ns) ou os quadros de vídeo do encarte em anexo.
            
            FOCO TOTAL (Whitelist):
            Extraia APENAS itens de supermercado das categorias: ALIMENTOS, CARNES, HORTIFRUTI, PADARIA, BEBIDAS, HIGIENE, LIMPEZA, FRIOS_LATICINIOS, PET.
            
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
            - Para cada produto extraído, identifique as coordenadas da foto do produto (o pacote, garrafa ou item físico propriamente dito, excluindo o preço ou outras decorações) e retorne como "box_2d" no formato [ymin, xmin, ymax, xmax] normalizado de 0 a 1000. Seja o mais restrito e justo possível à embalagem/produto em si.
            - Informe no campo "quadro_index" o índice (base 0) da imagem ou frame do vídeo onde o produto foi identificado e de onde o box_2d foi calculado.
            
            Padrão de saída JSON:
            {
                "itens": [
                    {
                        "produto": "NOME",
                        "preco": 0.0,
                        "unidade": "un",
                        "categoria": "ALIMENTOS/CARNES/HORTIFRUTI/PADARIA/BEBIDAS/HIGIENE/LIMPEZA/FRIOS_LATICINIOS/PET",
                        "validade": "DATA SE HOUVER",
                        "box_2d": [ymin, xmin, ymax, xmax],
                        "quadro_index": 0
                    }
                ]
            }
            Retorne APENAS o JSON puro.
            """
            gemini_parts.append(prompt_vision)

            # 5. Roteamento (Utilizando Gemini 3.1 Flash-Lite no Vertex AI para visão computacional)
            modelo_escolhido = "gemini-3.1-flash-lite"
            
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

                        # --- RECORTE DE IMAGEM VIA IA ---
                        img_bytes_original = None
                        box_2d = item.get("box_2d")
                        try:
                            quadro_index = int(item.get("quadro_index", 0))
                        except Exception:
                            quadro_index = 0

                        if box_2d and len(box_2d) == 4:
                            if frames_b64:
                                if 0 <= quadro_index < len(frames_b64):
                                    import base64
                                    img_bytes_original = base64.b64decode(frames_b64[quadro_index])
                            elif tmp_path and os.path.exists(tmp_path) and not is_video:
                                with open(tmp_path, "rb") as f:
                                    img_bytes_original = f.read()

                        imagem_url_crop = ""
                        if img_bytes_original:
                            temp_prod_id = normalizar_nome(item.get("produto", ""), item.get("unidade", "un"))
                            imagem_url_crop = upload_imagem_cortada(
                                img_bytes_original, box_2d, temp_prod_id,
                                item.get("produto", ""), item.get("unidade", "un"), item.get("marca", "")
                            )

                        res = salvar_produto_e_oferta(
                            nome=item.get("produto", ""),
                            preco=preco,
                            unidade=item.get("unidade", "un"),
                            categoria=item.get("categoria", "Geral"),
                            supermercado_id=supermercado_id,
                            loja=loja_nome,
                            metodo="gemini_vision",
                            imagem_api=imagem_url_crop if imagem_url_crop else item.get("imagem", ""),
                            validade=item.get("validade"),
                            post_id=post_id,
                            imagem_origem="auto_crop" if imagem_url_crop else ""
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
