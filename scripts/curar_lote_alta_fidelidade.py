import sys
import os
import io
import time
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from PIL import Image, ImageOps

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore, storage
from playwright.sync_api import sync_playwright

from scripts.central_imagens import inicializar_firebase, limpar_termo_busca, processar_e_otimizar_imagem

# Domínios confiáveis com packshots de e-commerce e varejo
DOMINIOS_PRIORITARIOS = [
    "vtexassets.com", "vteximg.com.br", "agilecdn.com.br", "carrefour",
    "ibassets.com.br", "paodeacucar.com", "sonda.com.br", "muffato",
    "araujo.com.br", "drogasil.com.br", "clinoff.com.br", "fbitsstatic.net",
    "clubeextra.com.br", "supermambo.com.br", "nagumo.com.br", "shibata.com.br",
    "mercadolivre.com", "mlstatic.com", "irmaosgoncalves.com.br"
]

DOMINIOS_BLOQUEADOS = [
    "pinterest.", "facebook.", "instagram.", "youtube.", "tiktok.",
    "wikipedia.org", "wikimedia.org", "g1.globo.com", "uol.com.br",
    "noticias", "blogspot.", "wordpress.", "areacar.eu"
]

def buscar_candidatos_bing(page, termo_busca: str, max_resultados: int = 6) -> list:
    """Busca imagens de alta resolução no Bing Images usando o navegador headless."""
    query = f"{termo_busca} supermercado"
    url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}&form=HDRSC2&first=1"
    
    candidatos = []
    try:
        page.goto(url, timeout=18000)
        page.wait_for_selector("a.iusc", timeout=8000)
        elements = page.query_selector_all("a.iusc")
        
        for el in elements:
            m_attr = el.get_attribute("m")
            if not m_attr:
                continue
            try:
                data = json.loads(m_attr)
                murl = data.get("murl")
                if not murl or not murl.startswith("http"):
                    continue
                    
                # Ignora domínios bloqueados
                if any(b in murl.lower() for b in DOMINIOS_BLOQUEADOS):
                    continue
                    
                # Prioriza ou adiciona
                candidatos.append(murl)
                if len(candidatos) >= max_resultados * 2:
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"      ⚠️ Falha ao consultar Bing Images para '{termo_busca}': {e}")
        
    # Reordena colocando domínios prioritários no topo
    prioritarios = [u for u in candidatos if any(p in u.lower() for p in DOMINIOS_PRIORITARIOS)]
    demais = [u for u in candidatos if u not in prioritarios]
    return (prioritarios + demais)[:max_resultados]

def curar_produto(db, bucket, page, prod_id: str, prod_nome: str) -> bool:
    """Busca, valida, trata em 400x400 e sincroniza a imagem de um produto."""
    termo = limpar_termo_busca(prod_nome)
    print(f"\n📦 [{prod_id}]")
    print(f"   Nome Original: {prod_nome}")
    print(f"   Termo de Busca: '{termo}'")
    
    urls = buscar_candidatos_bing(page, termo)
    if not urls:
        # Tenta uma busca mais aberta apenas com as 3 primeiras palavras do termo
        palavras = termo.split()
        if len(palavras) > 3:
            termo_curto = " ".join(palavras[:3])
            print(f"   🔄 Tentando fallback mais curto: '{termo_curto}'")
            urls = buscar_candidatos_bing(page, termo_curto)
            
    if not urls:
        print("   ❌ Nenhuma imagem comercial encontrada.")
        return False
        
    buffer_img = None
    url_vencedora = None
    
    for idx, u in enumerate(urls, 1):
        try:
            print(f"   🔍 Testando [{idx}/{len(urls)}]: {u[:75]}...")
            buf = processar_e_otimizar_imagem(u, tamanho=(400, 400), qualidade=80)
            if buf:
                buffer_img = buf
                url_vencedora = u
                break
        except Exception as e:
            continue
            
    if not buffer_img:
        print("   ❌ Nenhuma das imagens candidatas pôde ser baixada/otimizada.")
        return False
        
    try:
        blob_path = f"produtos/{prod_id}.jpg"
        blob = bucket.blob(blob_path)
        blob.upload_from_file(buffer_img, content_type="image/jpeg")
        blob.make_public()
        timestamp = int(time.time())
        public_url = f"{blob.public_url}?t={timestamp}"
        
        # 1. Atualiza no Firestore: Produtos
        db.collection("produtos").document(prod_id).set({
            "imagem_url": public_url,
            "imagem_origem": "estudio_400x400",
            "imagem_resolucao": "400x400",
            "atualizado_em": datetime.now()
        }, merge=True)
        
        # 2. Atualiza no Firestore: Ofertas associadas
        ofs = list(db.collection("ofertas").where("produto_id", "==", prod_id).stream())
        for o in ofs:
            db.collection("ofertas").document(o.id).update({
                "imagem_url": public_url,
                "imagem_resolucao": "400x400",
                "atualizado_em": datetime.now()
            })
            
        print(f"   ✅ SUCESSO! 400x400 px salvo no Storage e propagado para {len(ofs)} oferta(s)!")
        return True
    except Exception as e:
        print(f"   ❌ Erro ao salvar no Firebase Storage/Firestore: {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 INICIANDO CURADORIA INTELIGENTE DE ALTA FIDELIDADE (400x400)")
    print("=" * 60)
    
    db, bucket = inicializar_firebase()
    hoje = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Mapeia todos os produtos que possuem ofertas ativas sem foto do Storage
    produtos_alvo = {}
    
    for doc in db.collection("ofertas").where("expira_em", ">=", hoje).stream():
        d = doc.to_dict()
        img = d.get("imagem_url") or ""
        if "firebasestorage" not in img:
            pid = d.get("produto_id", "")
            if pid and pid not in produtos_alvo:
                p_doc = db.collection("produtos").document(pid).get()
                p_nome = p_doc.to_dict().get("nome") if p_doc.exists else pid
                produtos_alvo[pid] = p_nome
                
    # Adiciona itens conhecidos pendentes caso existam
    if "abs-clinoff-noturno-suave-ca-l8p7-uni" not in produtos_alvo:
        p_doc = db.collection("produtos").document("abs-clinoff-noturno-suave-ca-l8p7-uni").get()
        if p_doc.exists:
            produtos_alvo["abs-clinoff-noturno-suave-ca-l8p7-uni"] = p_doc.to_dict().get("nome", "ABS CLIN-OFF NOTURNO SUAVE C/A L8P7 (uni)")
            
    total_alvo = len(produtos_alvo)
    print(f"📋 Total de produtos identificados para curadoria: {total_alvo}")
    
    sucesso = 0
    falhas = 0
    
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        
        for idx, (prod_id, prod_nome) in enumerate(produtos_alvo.items(), 1):
            print(f"\n--- [{idx}/{total_alvo}] ---")
            ok = curar_produto(db, bucket, page, prod_id, prod_nome)
            if ok:
                sucesso += 1
            else:
                falhas += 1
            # Pausa suave anti-bloqueio
            time.sleep(1)
            
        browser.close()
        
    print("\n" + "=" * 60)
    print(f"🏁 CURADORIA CONCLUÍDA:")
    print(f"   ✅ Sucesso: {sucesso}/{total_alvo} ({sucesso/total_alvo*100:.1f}%)")
    print(f"   ❌ Falhas:  {falhas}/{total_alvo}")
    print("=" * 60)

if __name__ == "__main__":
    main()
