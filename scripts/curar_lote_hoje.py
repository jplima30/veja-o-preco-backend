import os
import sys

# Garante saída em tempo real sem buffer
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import time
import re
import io
import requests
from datetime import datetime
from PIL import Image, ImageOps

# Adiciona paths para importação
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

from scripts.central_imagens import inicializar_firebase, processar_e_otimizar_imagem

def limpar_nome_busca(nome: str) -> str:
    n = nome
    n = re.sub(r'\s*\((un|kg|quilo|cada|unidade|g|ml|l|pacote)\)\s*$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\s+-\s+(un|kg|quilo|cada|unidade|g|ml|l|pacote)\s*$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'[-/\\_,\.]', ' ', n)
    n = re.sub(r'\b(un|kg|cada|unidades|unidade)\b', '', n, flags=re.IGNORECASE)
    return ' '.join(n.split())

def executar_curadoria_hoje():
    db, bucket = inicializar_firebase()
    hoje = datetime.now()
    
    print("⏳ Carregando ofertas vigentes...", flush=True)
    ofertas_docs = list(db.collection("ofertas").where("expira_em", ">=", hoje).stream())
    print(f"✅ {len(ofertas_docs)} ofertas vigentes carregadas.", flush=True)
    
    # Agrupa por produto_id para evitar trabalho duplicado
    produtos_para_curar = {}
    for of_doc in ofertas_docs:
        d = of_doc.to_dict()
        img = d.get("imagem_url", "")
        pid = d.get("produto_id")
        nome = d.get("produto_nome")
        
        if not pid:
            continue
            
        # Critério: se ainda não tem o selo verde (?t=)
        if "?t=" not in img:
            if pid not in produtos_para_curar:
                produtos_para_curar[pid] = {
                    "nome": nome,
                    "img_atual": img,
                    "ofertas_ids": [of_doc.id]
                }
            else:
                produtos_para_curar[pid]["ofertas_ids"].append(of_doc.id)
                
    total = len(produtos_para_curar)
    print(f"🎯 Total de produtos únicos pendentes para curar: {total}", flush=True)
    
    if total == 0:
        print("🎉 Todas as ofertas vigentes já estão curadas com selo verde (?t=)!", flush=True)
        return
        
    print("\n🚀 Abrindo Chrome visível com perfil persistente...", flush=True)
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'playwright_profile'))
    context = pw.chromium.launch_persistent_context(
        profile_dir,
        headless=False,
        channel='chrome',
        args=['--disable-blink-features=AutomationControlled'],
        ignore_default_args=['--enable-automation'],
        locale='pt-BR'
    )
    page = context.pages[0] if context.pages else context.new_page()
    
    # Entra no Google e navega até a aba Imagens
    try:
        page.goto('https://www.google.com', timeout=15000)
        page.wait_for_timeout(1000)
        q_init = page.wait_for_selector('textarea[name="q"], input[name="q"]', timeout=6000)
        q_init.fill('supermercado')
        page.keyboard.press('Enter')
        page.wait_for_load_state('domcontentloaded')
        
        img_tab = page.wait_for_selector('a:has-text("Imagens"), a:has-text("Images")', timeout=6000)
        img_tab.click()
        page.wait_for_load_state('domcontentloaded')
        page.wait_for_timeout(1000)
    except Exception as e_init:
        print(f"⚠️ Aviso ao abrir aba Imagens: {e_init}", flush=True)
        
    sucessos_google = 0
    sucessos_recorte = 0
    falhas = 0
    
    itens = list(produtos_para_curar.items())
    
    try:
        for idx, (pid, info) in enumerate(itens):
            nome_original = info["nome"]
            nome_busca = limpar_nome_busca(nome_original)
            print(f"\n[{idx+1}/{total}] 🔍 Curando: {nome_original} (ID: {pid})", flush=True)
            
            buffer_otimizado = None
            
            try:
                # Garante que está no Google Imagens antes de buscar
                if "udm=2" not in page.url and "tbm=isch" not in page.url:
                    page.goto('https://www.google.com/imghp?hl=pt-BR', timeout=10000)
                    page.wait_for_timeout(800)
                    
                q_input = page.wait_for_selector('textarea[name="q"], input[name="q"]', timeout=5000)
                q_input.fill(f"{nome_busca} supermercado")
                page.keyboard.press('Enter')
                page.wait_for_load_state('domcontentloaded')
                page.wait_for_timeout(1200)
                
                # Seleciona ESTRITAMENTE cards de thumbnail de produtos
                cards = page.query_selector_all('div.bFtXbb img, div.uhHOwf img')
                print(f"   Encontrados {len(cards)} cards no grid.", flush=True)
                
                for c_idx, card in enumerate(cards[:4]):
                    try:
                        card.evaluate('el => el.click()')
                        page.wait_for_timeout(1000)
                        
                        high_res = page.evaluate('''() => {
                            const els = Array.from(document.querySelectorAll('img[jsname="kn3ccd"], img.sFlh5c[src^="http"]'));
                            for (const el of els) {
                                const s = el.src || '';
                                if (s.startsWith('http') && !s.includes('gstatic.com') && !s.includes('google.com')) {
                                    return s;
                                }
                            }
                            return '';
                        }''')
                        
                        if high_res:
                            banned = ['wikipedia', 'wikimedia', 'noticia', 'g1.globo', 'facebook', 'instagram', 'paintingvalley']
                            if any(b in high_res.lower() for b in banned):
                                continue
                            print(f"   👉 Candidato {c_idx+1} HD: {high_res[:70]}...", flush=True)
                            buffer_otimizado = processar_e_otimizar_imagem(high_res, tamanho=(400, 400), qualidade=80)
                            sucessos_google += 1
                            break
                    except Exception as e_card:
                        continue
                        
            except Exception as e_search:
                print(f"   ⚠️ Falha na busca: {e_search}", flush=True)
                
            # Fallback: Se não encontrou foto oficial no Google, reprocessa o recorte existente para 400x400 HD
            if not buffer_otimizado:
                if info["img_atual"]:
                    try:
                        print("   🔄 Reprocessando recorte do encarte para 400x400 com fundo branco...", flush=True)
                        buffer_otimizado = processar_e_otimizar_imagem(info["img_atual"], tamanho=(400, 400), qualidade=80)
                        sucessos_recorte += 1
                    except Exception as e_rec:
                        print(f"   ❌ Falha ao reprocessar recorte: {e_rec}", flush=True)
                        falhas += 1
                        continue
                else:
                    falhas += 1
                    continue
                    
            # Upload para o Storage e Firestore
            try:
                blob = bucket.blob(f"produtos/{pid}.jpg")
                blob.upload_from_string(buffer_otimizado.getvalue(), content_type="image/jpeg")
                blob.make_public()
                
                ts = int(time.time())
                public_url = f"{blob.public_url}?t={ts}"
                
                # Atualiza produto
                db.collection("produtos").document(pid).update({
                    "imagem_url": public_url,
                    "imagem_origem": "curadoria_manual",
                    "atualizado_em": datetime.now()
                })
                
                # Atualiza todas as ofertas vinculadas
                for of_id in info["ofertas_ids"]:
                    db.collection("ofertas").document(of_id).update({
                        "imagem_url": public_url
                    })
                    
                kb = len(buffer_otimizado.getvalue()) / 1024.0
                print(f"   ✅ SALVO! 400x400 ({kb:.1f} KB) com selo verde (?t={ts})", flush=True)
                
            except Exception as e_up:
                print(f"   ❌ Erro ao salvar Firebase: {e_up}", flush=True)
                falhas += 1
                
    finally:
        try:
            context.close()
            pw.stop()
        except:
            pass
            
    print("\n" + "="*60, flush=True)
    print("🏁 CURADORIA COMPLETA CONCLUÍDA!", flush=True)
    print(f"   ✨ Imagens oficiais de estúdio (Google Imagens): {sucessos_google}", flush=True)
    print(f"   🖼️  Recortes reprocessados para 400x400 HD: {sucessos_recorte}", flush=True)
    print(f"   ❌ Falhas: {falhas}", flush=True)
    print("="*60, flush=True)

if __name__ == "__main__":
    executar_curadoria_hoje()
