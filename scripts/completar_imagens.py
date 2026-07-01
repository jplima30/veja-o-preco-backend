import sys
import os
import requests
import io
import urllib.parse
import time
from datetime import datetime
from PIL import Image, ImageOps

# Adiciona as pastas corretas ao Path para importação do Firebase Admin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore, storage

def inicializar_firebase():
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
    return firestore.client(), storage.bucket("veja-o-preco.firebasestorage.app")

def buscar_duckduckgo_images(nome_produto: str) -> list:
    """
    Busca até 4 URLs de imagens no DuckDuckGo de forma gratuita e sem chaves de API.
    """
    import re
    
    # Limpa nome para busca
    n = nome_produto
    n = re.sub(r'\s*\((un|kg|quilo|cada|unidade|g|ml|l|pacote)\)\s*$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\s+-\s+(un|kg|quilo|cada|unidade|g|ml|l|pacote)\s*$', '', n, flags=re.IGNORECASE)
    query = n.strip()

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url_token = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&iax=images&ia=images"
    try:
        # Intervalo curto de 0.5s para evitar ser bloqueado temporariamente pelo DuckDuckGo
        time.sleep(0.5)
        res = requests.get(url_token, headers=headers, timeout=5)
        if res.status_code != 200:
            return []
        match = re.search(r"vqd=([\d-]+)&", res.text)
        if not match:
            match = re.search(r'vqd\s*=\s*[\'"]([^\'"]+)[\'"]', res.text)
            if not match:
                return []
        vqd = match.group(1)
        
        url_images = f"https://duckduckgo.com/i.js?l=wt-wt&o=json&q={urllib.parse.quote(query)}&vqd={vqd}&f=,,,&p=1"
        res_images = requests.get(url_images, headers=headers, timeout=5)
        if res_images.status_code == 200:
            dados = res_images.json()
            results = dados.get("results", [])
            urls = []
            for r in results:
                img_url = r.get("image", "")
                if img_url and img_url.startswith("http") and img_url not in urls:
                    urls.append(img_url)
                    if len(urls) >= 4:
                        break
            return urls
    except Exception:
        pass
    return []

def processar_e_otimizar_imagem(url_imagem: str) -> io.BytesIO:
    """
    Baixa uma imagem da internet, ajusta sua proporção com preenchimento branco (200x200) e comprime para JPEG 75%.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url_imagem, headers=headers, timeout=10)
    resp.raise_for_status()
    
    img_bytes = io.BytesIO(resp.content)
    with Image.open(img_bytes) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Redimensionamento 200x200 preservando proporção
        img_redimensionada = ImageOps.pad(img, (200, 200), color="white", centering=(0.5, 0.5))
        
        output = io.BytesIO()
        img_redimensionada.save(output, "JPEG", quality=75)
        output.seek(0)
        return output

def curar_imagens():
    print("=========================================================")
    print("🧹 INICIANDO HIGIENIZAÇÃO E CURAÇÃO DE IMAGENS DE PRODUTOS")
    print("=========================================================\n")
    
    # Seleção de Modo
    print("Selecione o modo de curação desejado:")
    print("  [1] Apenas produtos totalmente SEM IMAGEM (Crítico) [Padrão]")
    print("  [2] Apenas produtos com recortes RECENTES da IA (auto_crop)")
    print("  [3] Apenas recortes da IA que já foram ACEITOS anteriormente (auto_crop_aceito)")
    print("  [4] Tudo (Sem imagem + Recortes recentes + Recortes aceitos)")
    print("  [5] PILOTO AUTOMÁTICO (Busca no DuckDuckGo Images em lote 100% silencioso)")
    
    opcao_modo = input("\n👉 Digite a opção desejada [1-5] (ou Enter para a Padrão 1): ").strip()
    if not opcao_modo:
        opcao_modo = "1"
        
    if opcao_modo not in ("1", "2", "3", "4", "5"):
        print("❌ Opção inválida. Encerrando.")
        return

    db, bucket = inicializar_firebase()
    
    # 1. Obter todos os produtos do Firestore
    print("\n⏳ Carregando produtos do Firestore...")
    produtos_ref = db.collection("produtos")
    docs = list(produtos_ref.stream())
    print(f"✅ {len(docs)} produtos carregados.\n")
    
    # 2. Filtrar produtos de acordo com o modo selecionado
    produtos_pendentes = []
    for doc in docs:
        d = doc.to_dict()
        url = d.get("imagem_url", "")
        origem = d.get("imagem_origem", "")
        
        incluir = False
        if opcao_modo == "1":
            # Apenas sem imagem
            incluir = (not url)
        elif opcao_modo == "2":
            # Apenas recortes recentes
            incluir = (url and origem == "auto_crop")
        elif opcao_modo == "3":
            # Apenas recortes aceitos
            incluir = (url and origem == "auto_crop_aceito")
        elif opcao_modo == "4":
            # Tudo
            incluir = (not url or origem in ("auto_crop", "auto_crop_aceito", "padrao", ""))
        elif opcao_modo == "5":
            # Piloto automático (sem imagem ou auto_crop)
            incluir = (not url or origem == "auto_crop")
            
        if incluir and not doc.id.startswith("_"):
            produtos_pendentes.append((doc.id, d))
            
    if not produtos_pendentes:
        print("🎉 Nenhum produto pendente de curação no modo selecionado!")
        return
        
    print(f"📂 Encontrados {len(produtos_pendentes)} produtos correspondentes.")
    print("---------------------------------------------------------")
    
    total_atualizados = 0
    
    for i, (prod_id, prod_data) in enumerate(produtos_pendentes):
        nome = prod_data.get("nome", "Sem nome")
        unidade = prod_data.get("unidade", "un")
        origem_atual = prod_data.get("imagem_origem", "desconhecida")
        url_atual = prod_data.get("imagem_url", "")
        # Busca supermercados associados na coleção de ofertas
        lojas = set()
        try:
            query_lojas = db.collection("ofertas").where("produto_id", "==", prod_id).stream()
            for doc_of in query_lojas:
                data_of = doc_of.to_dict()
                loja = data_of.get("loja", "")
                if loja:
                    lojas.add(loja)
        except Exception as e_query:
            pass

        while True:  # Loop de retentativa para o mesmo produto
            print(f"\n📦 [{i+1}/{len(produtos_pendentes)}] Produto: {nome} ({unidade})")
            print(f"   ID: {prod_id}")
            if lojas:
                print(f"   🛒 Supermercado(s): {', '.join(sorted(lojas))}")
            print(f"   Status Atual: {origem_atual.upper()}")
            if url_atual:
                print(f"   Imagem Atual: {url_atual}")
            
            url_selecionada = ""
            origem_selecionada = ""
            pular_produto = False
            buffer_otimizado = None
            
            # Passo 1: Busca automática de imagens no DuckDuckGo
            print("   🔍 Buscando no DuckDuckGo Images...")
            urls_ddg = buscar_duckduckgo_images(nome)
            
            if urls_ddg:
                print(f"   🌐 Encontradas {len(urls_ddg)} imagens no DuckDuckGo.")
                sucesso_download = False
                
                for idx, url_temp in enumerate(urls_ddg):
                    print(f"     [Tentativa {idx+1}/{len(urls_ddg)}] Testando: {url_temp}")
                    
                    if opcao_modo == "5":
                        # Piloto Automático: tenta baixar silenciosamente
                        try:
                            buffer_otimizado = processar_e_otimizar_imagem(url_temp)
                            url_selecionada = url_temp
                            origem_selecionada = "manual"
                            sucesso_download = True
                            print("     🤖 [AUTO-PILOTO] Imagem baixada e otimizada com sucesso.")
                            break
                        except Exception as e_proc:
                            print(f"     ❌ Falha ao processar link {idx+1}: {e_proc}")
                    else:
                        # Modo Interativo: pergunta ao usuário
                        opcao = input(f"     👉 Usar essa imagem {idx+1}? [Y] Sim (Enter) / [N] Tentar próxima / [S] Pular produto / [A] Aceitar recorte atual: ").strip().lower()
                        if opcao == "" or opcao == "y" or opcao == "yes":
                            try:
                                buffer_otimizado = processar_e_otimizar_imagem(url_temp)
                                url_selecionada = url_temp
                                origem_selecionada = "manual"
                                sucesso_download = True
                                break
                            except Exception as e_proc:
                                print(f"     ❌ Erro ao baixar essa imagem: {e_proc}. Tente outra.")
                        elif opcao == "a" or opcao == "aceitar":
                            if url_atual:
                                print("   💾 Marcando recorte atual como aceito no Firestore...")
                                ref_doc = produtos_ref.document(prod_id)
                                ref_doc.update({
                                    "imagem_origem": "auto_crop_aceito",
                                    "atualizado_em": datetime.now()
                                })
                                print("   ✅ Status atualizado para AUTO_CROP_ACEITO.")
                            else:
                                print("   ⚠️ Este produto não possui um recorte de imagem para aceitar. Pulo realizado.")
                            pular_produto = True
                            break
                        elif opcao == "s" or opcao == "skip":
                            print("   ⏭️ Produto pulado.")
                            pular_produto = True
                            break
                
                if pular_produto:
                    break
                    
                if not sucesso_download and not pular_produto:
                    print("   ❌ Nenhuma das imagens do DuckDuckGo pôde ser baixada.")
            else:
                print("   ❌ Não encontrado no DuckDuckGo.")
                
            if pular_produto:
                break
                
            # Passo 2: Entrada manual caso nenhuma automática tenha sido bem-sucedida
            if not url_selecionada:
                if opcao_modo == "5":
                    break
                opcao_manual = input("   🔗 Cole a URL da imagem da internet (ou aperte Enter para PULAR, ou digite 'A' para aceitar o recorte atual): ").strip()
                if opcao_manual.lower() == "a":
                    if url_atual:
                        print("   💾 Marcando recorte atual como aceito no Firestore...")
                        ref_doc = produtos_ref.document(prod_id)
                        ref_doc.update({
                            "imagem_origem": "auto_crop_aceito",
                            "atualizado_em": datetime.now()
                        })
                        print("   ✅ Status atualizado para AUTO_CROP_ACEITO.")
                        break
                    else:
                        print("   ⚠️ Este produto não possui um recorte de imagem para aceitar.")
                        continue
                if not opcao_manual:
                    print("   ⏭️ Produto pulado.")
                    break
                try:
                    buffer_otimizado = processar_e_otimizar_imagem(opcao_manual)
                    url_selecionada = opcao_manual
                    origem_selecionada = "manual"
                except Exception as e_proc:
                    print(f"   ❌ ERRO ao processar URL manual: {e_proc}")
                    continue
                    
            # Passo 3: Fazer Upload dos dados (o buffer_otimizado já está preenchido)
            try:
                print("   ☁️ Fazendo upload para o Firebase Storage...")
                blob_name = f"produtos/{prod_id}.jpg"
                blob = bucket.blob(blob_name)
                blob.upload_from_string(buffer_otimizado.getvalue(), content_type="image/jpeg")
                blob.make_public()
                public_url = blob.public_url
                
                print("   💾 Salvando metadados no Firestore...")
                ref_doc = produtos_ref.document(prod_id)
                ref_doc.update({
                    "imagem_url": public_url,
                    "imagem_origem": origem_selecionada,
                    "atualizado_em": datetime.now()
                })
                
                tamanho_kb = len(buffer_otimizado.getvalue()) / 1024.0
                print(f"   ✅ SUCESSO! Imagem curada salva com sucesso ({tamanho_kb:.2f} KB)!")
                total_atualizados += 1
                break
                
            except Exception as e_up:
                print(f"   ❌ ERRO ao fazer upload ou salvar Firestore: {e_up}")
                break

if __name__ == "__main__":
    try:
        curar_imagens()
    except KeyboardInterrupt:
        print("\n\n👋 Operação cancelada pelo usuário.")
        sys.exit(0)
