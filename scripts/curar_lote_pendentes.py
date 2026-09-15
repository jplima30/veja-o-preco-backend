import sys
import os
import io
import json
import time
import urllib.parse
import re
from datetime import datetime
from PIL import Image, ImageOps

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore, storage
from playwright.sync_api import sync_playwright

from scripts.central_imagens import limpar_termo_busca, processar_e_otimizar_imagem

BANNED_DOMAINS = [
    "youtube.com", "ytimg.com", "uol.com", "mundoeducacao", "pinimg.com", "pinterest",
    "shutterstock", "freepik", "istock", "dreamstime", "depositphotos", "podcast",
    "noticia", "g1.globo", "receita", "caseiro", "diy", "blog", "wikihow", "wikipedia",
    "facebook.com", "instagram.com", "tiktok.com", "formula", "quimica", "desenho",
    "canva.com", "areacar.eu", "eaglelandingfl.com", "honeybeehobbyist.com"
]

ECOMMERCE_WHITELIST = [
    "vtex", "agilecdn", "carrefour", "paodeacucar", "sonda", "drogasil", "raia", "araujo",
    "extrabom", "mambo", "mercantil", "susercontent", "awsli.com", "efacil", "clubeextra",
    "atacadao", "supermercado", "comprebem", "zonasul", "martminas", "savegnago", "nagumo",
    "guanabara", "bistek", "supernosso", "prezunic", "tendatacadista", "giga", "assai",
    "mateus", "davo", "superpao", "condor", "supermuffato", "superadega", "muffato",
    "boticario", "belezanaweb", "epocacosmeticos", "panvel", "drogariasaopaulo", "paguemenos",
    "ultrafarma", "drogal", "nissei", "venancio", "supernossoio", "sondadelivery", "hiperideal"
]

def inicializar():
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
    return firestore.client(), storage.bucket("veja-o-preco.firebasestorage.app")

def normalizar_siglas(n):
    n = re.sub(r'^(abs\.|absorv\.|abs\b|absorv\b)\s*', 'Absorvente ', n, flags=re.I)
    n = re.sub(r'^(desinf\.|desinf\b)\s*', 'Desinfetante ', n, flags=re.I)
    n = re.sub(r'^(amac\.|amaciante\b)\s*', 'Amaciante ', n, flags=re.I)
    n = re.sub(r'^(sh\.|shamp\.|shampoo\b)\s*', 'Shampoo ', n, flags=re.I)
    n = re.sub(r'^(cond\.|condic\.|condicionador\b)\s*', 'Condicionador ', n, flags=re.I)
    n = re.sub(r'^(sabon\.|sab\.|sabonete\b)\s*', 'Sabonete ', n, flags=re.I)
    n = re.sub(r'^(deterg\.|det\.|detergente\b)\s*', 'Detergente ', n, flags=re.I)
    n = re.sub(r'^(limp\.|limpador\b)\s*', 'Limpador ', n, flags=re.I)
    return n

def buscar_imagens(page, nome_produto):
    nome_expandido = normalizar_siglas(nome_produto)
    query = limpar_termo_busca(nome_expandido)
    urls = []
    
    try:
        termo_encoded = urllib.parse.quote(query + " produto supermercado")
        url_bing = f"https://www.bing.com/images/search?q={termo_encoded}&qft=+filterui:photo-photo"
        page.goto(url_bing, wait_until="domcontentloaded", timeout=12000)
        page.wait_for_timeout(1000)
        
        iusc_links = page.query_selector_all("a.iusc")
        for a in iusc_links:
            m_attr = a.get_attribute("m")
            if m_attr:
                try:
                    m_data = json.loads(m_attr)
                    murl = m_data.get("murl")
                    if murl and murl.startswith("http"):
                        # Verifica se não é domínio banido e pertence à whitelist de e-commerce
                        if any(ban in murl.lower() for ban in BANNED_DOMAINS):
                            continue
                        if any(eco in murl.lower() for eco in ECOMMERCE_WHITELIST):
                            urls.append(murl)
                except Exception:
                    continue
    except Exception as e:
        print(f"   ⚠️ Erro na busca: {e}")
        
    return urls[:8]

def main():
    db, bucket = inicializar()
    print("⏳ Carregando produtos pendentes do Firestore...")
    
    docs = list(db.collection("produtos").stream())
    pendentes = []
    for doc in docs:
        if doc.id.startswith("_"):
            continue
        d = doc.to_dict()
        url = d.get("imagem_url", "")
        origem = d.get("imagem_origem", "desconhecida")
        is_external_api = (origem == "api_loja" and url and "googleapis.com" not in url)
        # Processa produtos sem imagem ou com imagem externa
        if not url or is_external_api or origem == "desconhecida":
            pendentes.append((doc.id, d))
            
    print(f"📦 Total de produtos pendentes para curar: {len(pendentes)}")
    if not pendentes:
        print("🎉 Nenhum produto pendente!")
        return

    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'playwright_profile'))
    
    sucessos = 0
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            profile_dir,
            headless=True,
            args=['--disable-blink-features=AutomationControlled'],
            locale='pt-BR'
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        
        for idx, (prod_id, prod_data) in enumerate(pendentes):
            nome = prod_data.get("nome", "Sem nome")
            print(f"\n[{idx+1}/{len(pendentes)}] Processando: {nome} (ID: {prod_id})")
            
            candidatos = buscar_imagens(page, nome)
            if not candidatos:
                print(f"   ❌ Nenhuma imagem de e-commerce oficial encontrada para: {nome}")
                continue
                
            print(f"   🌐 {len(candidatos)} imagens de e-commerce encontradas. Testando download...")
            buffer_otimizado = None
            url_usada = None
            
            for c_url in candidatos:
                try:
                    buffer_otimizado = processar_e_otimizar_imagem(c_url)
                    url_usada = c_url
                    print(f"   ✅ Imagem comercial aprovada e otimizada (400x400): {c_url[:75]}")
                    break
                except Exception as e_proc:
                    continue
                    
            if not buffer_otimizado:
                print(f"   ❌ Falha ao processar imagens para {nome}")
                continue
                
            # Upload para o Storage
            try:
                blob_path = f"produtos/{prod_id}.jpg"
                blob = bucket.blob(blob_path)
                blob.upload_from_file(buffer_otimizado, content_type="image/jpeg")
                blob.make_public()
                public_url = f"{blob.public_url}?t={int(time.time())}"
                
                # Atualiza produto no Firestore
                db.collection("produtos").document(prod_id).update({
                    "imagem_url": public_url,
                    "imagem_origem": "manual",
                    "atualizado_em": datetime.now()
                })
                
                # Sincroniza ofertas desse produto
                of_docs = db.collection("ofertas").where("produto_id", "==", prod_id).stream()
                total_of = 0
                for of in of_docs:
                    db.collection("ofertas").document(of.id).update({
                        "imagem_url": public_url,
                        "atualizado_em": datetime.now()
                    })
                    total_of += 1
                    
                print(f"   🎉 Salvo no Storage (400x400) e sincronizado com {total_of} oferta(s)!")
                sucessos += 1
            except Exception as e_up:
                print(f"   ❌ Erro de upload: {e_up}")
                
        ctx.close()
        
    print(f"\n=======================================================")
    print(f"🏁 Curadoria concluída: {sucessos}/{len(pendentes)} produtos atualizados com sucesso!")
    print(f"=======================================================")

if __name__ == "__main__":
    main()
