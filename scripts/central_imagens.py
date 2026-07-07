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
        # Intervalo preventivo rápido para o DuckDuckGo
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

def buscar_bing_images(nome_produto: str) -> list[str]:
    """
    Busca imagens no Bing como fallback gratuito caso o DuckDuckGo falhe ou bloqueie a requisição.
    """
    import re
    import urllib.parse
    import requests
    import json
    import html
    
    n = nome_produto
    n = re.sub(r'\s*\((un|kg|quilo|cada|unidade|g|ml|l|pacote)\)\s*$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\s+-\s+(un|kg|quilo|cada|unidade|g|ml|l|pacote)\s*$', '', n, flags=re.IGNORECASE)
    query = n.strip()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.bing.com/"
    }
    
    url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}"
    try:
        time.sleep(0.5)
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200:
            return []
            
        matches = re.findall(r'class=\"iusc\"[^>]*\s+m=\"([^\"]+)\"', res.text)
        urls = []
        for m in matches:
            try:
                obj = json.loads(html.unescape(m))
                img_url = obj.get("murl")
                if img_url and img_url.startswith("http") and img_url not in urls:
                    urls.append(img_url)
                    if len(urls) >= 4:
                        break
            except Exception:
                continue
        return urls
    except Exception:
        pass
    return []

def extrair_url_real(url: str) -> str:
    """
    Se a URL contiver um parâmetro 'url=' interno (comum em otimizadores Next.js como o da Drogasil),
    extrai e decodifica esse link para baixar direto do CDN e evitar bloqueios (HTTP 403).
    """
    try:
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        if "url" in query_params:
            url_interna = query_params["url"][0]
            if url_interna.startswith("http"):
                return url_interna
    except Exception:
        pass
    return url

def processar_e_otimizar_imagem(url_imagem: str) -> io.BytesIO:
    """
    Baixa uma imagem da internet ou abre um arquivo local do disco,
    ajusta sua proporção com preenchimento branco (200x200) e comprime para JPEG 75%.
    """
    import os
    import re
    
    # Limpa possíveis aspas e escapes de espaço que o terminal insere ao arrastar arquivo
    caminho_limpo = url_imagem.strip().strip("'\"")
    caminho_limpo = re.sub(r'\\(.)', r'\1', caminho_limpo)
    caminho_limpo = os.path.expanduser(caminho_limpo)
    
    if os.path.exists(caminho_limpo) and os.path.isfile(caminho_limpo):
        print(f"   📂 Carregando arquivo local: {caminho_limpo}")
        try:
            with open(caminho_limpo, "rb") as f:
                img_bytes = io.BytesIO(f.read())
        except Exception as e:
            raise Exception(f"Falha ao ler arquivo local: {e}")
    else:
        # Extrai o link limpo se for um link de redirecionamento/otimizador
        url_limpa = extrair_url_real(url_imagem)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site"
        }
        resp = requests.get(url_limpa, headers=headers, timeout=10)
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

def carregar_estatisticas_gerais(db) -> dict:
    """
    Carrega contagens gerais do catálogo de produtos e ofertas vigentes sem imagem.
    """
    stats = {
        "total_produtos": 0,
        "sem_imagem": 0,
        "auto_crop": 0,
        "auto_crop_aceito": 0,
        "curadas": 0,
        "total_ofertas_vigentes": 0,
        "ofertas_vigentes_sem_imagem": 0
    }
    
    try:
        # Estatísticas de produtos no catálogo mestre
        produtos_docs = db.collection("produtos").stream()
        for doc in produtos_docs:
            if doc.id.startswith("_"):
                continue
            stats["total_produtos"] += 1
            d = doc.to_dict()
            url = d.get("imagem_url", "")
            origem = d.get("imagem_origem", "")
            
            if not url:
                stats["sem_imagem"] += 1
            elif origem == "auto_crop":
                stats["auto_crop"] += 1
            elif origem == "auto_crop_aceito" or (origem == "api_loja" and "googleapis.com" not in url):
                stats["auto_crop_aceito"] += 1
            else:
                stats["curadas"] += 1
                
        # Estatísticas de ofertas vigentes no aplicativo
        hoje = datetime.now()
        ofertas_docs = db.collection("ofertas").where("expira_em", ">=", hoje).stream()
        for doc in ofertas_docs:
            stats["total_ofertas_vigentes"] += 1
            d = doc.to_dict()
            img = d.get("imagem_url", "").strip()
            if not img:
                stats["ofertas_vigentes_sem_imagem"] += 1
                
    except Exception as e:
        print(f"⚠️ Erro ao carregar estatísticas: {e}")
        
    return stats

def exibir_dashboard(stats: dict):
    print("=========================================================")
    print("🖼️  GERENCIADOR CENTRAL DE IMAGENS DO VEJAOPRECO")
    print("=========================================================")
    print("📊 PAINEL DE COBERTURA DE IMAGENS:")
    if stats["total_produtos"] > 0:
        p_sem = (stats["sem_imagem"] / stats["total_produtos"]) * 100
        p_crop = (stats["auto_crop"] / stats["total_produtos"]) * 100
        p_aceito = (stats["auto_crop_aceito"] / stats["total_produtos"]) * 100
        p_curadas = (stats["curadas"] / stats["total_produtos"]) * 100
        print(f"   • Produtos no Catálogo: {stats['total_produtos']}")
        print(f"     - Sem imagem:                  {stats['sem_imagem']} ({p_sem:.1f}%)")
        print(f"     - Recorte provisório (IA):     {stats['auto_crop']} ({p_crop:.1f}%)")
        print(f"     - Recorte aceito / APIs Ext.:  {stats['auto_crop_aceito']} ({p_aceito:.1f}%)")
        print(f"     - Imagens curadas de estúdio:  {stats['curadas']} ({p_curadas:.1f}%)")
    else:
        print("   • Nenhum produto cadastrado no catálogo.")
        
    print(f"   • Ofertas vigentes no aplicativo: {stats['total_ofertas_vigentes']}")
    if stats['total_ofertas_vigentes'] > 0:
        p_of_sem = (stats['ofertas_vigentes_sem_imagem'] / stats['total_ofertas_vigentes']) * 100
        print(f"     - Ofertas sem imagem vinculada: {stats['ofertas_vigentes_sem_imagem']} ({p_of_sem:.1f}%)")
    print("=========================================================\n")

def executar_sincronizacao(db):
    print("=========================================================")
    print("🔄 INICIANDO SINCRONIZAÇÃO DE IMAGENS DO CATALOGO PARA AS OFERTAS")
    print("=========================================================\n")
    
    print("⏳ Carregando produtos...")
    produtos_ref = db.collection("produtos")
    produtos = {doc.id: doc.to_dict() for doc in produtos_ref.stream() if not doc.id.startswith("_")}
    print(f"✅ {len(produtos)} produtos carregados.")
    
    print("⏳ Carregando ofertas...")
    ofertas_ref = db.collection("ofertas")
    ofertas = list(ofertas_ref.stream())
    print(f"✅ {len(ofertas)} ofertas carregadas.")
    
    total_atualizadas = 0
    for of_doc in ofertas:
        of_data = of_doc.to_dict()
        prod_id = of_data.get("produto_id")
        of_img = of_data.get("imagem_url", "")
        
        if prod_id in produtos:
            prod_data = produtos[prod_id]
            prod_img = prod_data.get("imagem_url", "")
            
            # Se o produto tem imagem curada no Firestore e a oferta tem imagem diferente/vazia
            if prod_img and of_img != prod_img:
                print(f"🔄 Sincronizando oferta: '{of_data.get('produto_nome')}'")
                print(f"   De: {of_img[:60]}...")
                print(f"   Para: {prod_img[:60]}...")
                
                of_doc.reference.update({
                    "imagem_url": prod_img
                })
                total_atualizadas += 1
                
    # Varredura pós-sincronização para detectar ofertas vigentes com imagens de APIs externas
    total_externas = 0
    hoje_limite = datetime.now().replace(tzinfo=None)
    for of_doc in ofertas:
        of_data = of_doc.to_dict()
        expira_em = of_data.get("expira_em")
        if expira_em:
            expira_naive = expira_em.replace(tzinfo=None) if hasattr(expira_em, "tzinfo") and expira_em.tzinfo else expira_em
            if expira_naive >= hoje_limite:
                prod_id = of_data.get("produto_id")
                final_img = of_data.get("imagem_url", "")
                if prod_id in produtos:
                    prod_img = produtos[prod_id].get("imagem_url", "")
                    if prod_img:
                        final_img = prod_img
                
                if final_img and "googleapis.com" not in final_img:
                    total_externas += 1
                    
    print("\n=========================================================")
    print("🏁 SINCRONIZAÇÃO CONCLUÍDA!")
    print(f"🔄 Total de ofertas sincronizadas: {total_atualizadas}")
    if total_externas > 0:
        print(f"⚠️  ALERTA: Existem {total_externas} ofertas ativas usando imagens externas (API Lojas)!")
        print("   Dica: execute a Opção 7 (Diagnóstico) no menu para listá-las.")
    print("=========================================================\n")

def executar_diagnostico(db):
    print("=========================================================")
    print("🔎 DIAGNÓSTICO DE IMAGENS DAS OFERTAS VIGENTES NO FIRESTORE")
    print("=========================================================\n")
    
    hoje = datetime.now()
    ofertas_ref = db.collection("ofertas").where("expira_em", ">=", hoje)
    docs = ofertas_ref.stream()
    
    sem_imagem = []
    imagem_externa = []
    total_vigentes = 0
    
    for doc in docs:
        total_vigentes += 1
        d = doc.to_dict()
        img = d.get("imagem_url", "").strip()
        
        if not img:
            sem_imagem.append((doc.id, d))
        elif "googleapis.com" not in img:
            imagem_externa.append((doc.id, d, img))
            
    print(f"📊 Total de ofertas vigentes encontradas: {total_vigentes}")
    print(f"❌ Total de ofertas vigentes SEM IMAGEM: {len(sem_imagem)}")
    print(f"⚠️  Total de ofertas vigentes COM IMAGEM EXTERNA (API Lojas): {len(imagem_externa)}")
    print("---------------------------------------------------------\n")
    
    if sem_imagem:
        print("📋 Amostra das primeiras 30 ofertas sem imagem:")
        for i, (doc_id, d) in enumerate(sem_imagem[:30]):
            loja = d.get("loja", "Desconhecida")
            nome = d.get("produto_nome", "Sem nome")
            preco = d.get("preco", 0)
            validade = d.get("validade", "Desconhecida")
            print(f"  [{i+1}] 🛒 {nome} - R$ {preco:.2f} ({loja}) | Validade: {validade}")
        
        if len(sem_imagem) > 30:
            print(f"\n... e mais {len(sem_imagem) - 30} ofertas sem imagem.")
        print()
            
    if imagem_externa:
        print("📋 Amostra das primeiras 30 ofertas com imagem externa (API Lojas):")
        for i, (doc_id, d, img_url) in enumerate(imagem_externa[:30]):
            loja = d.get("loja", "Desconhecida")
            nome = d.get("produto_nome", "Sem nome")
            preco = d.get("preco", 0)
            print(f"  [{i+1}] 🛒 {nome} - R$ {preco:.2f} ({loja})")
            print(f"      🔗 URL: {img_url}")
            
        if len(imagem_externa) > 30:
            print(f"\n... e mais {len(imagem_externa) - 30} ofertas com imagem externa.")
    
    if not sem_imagem and not imagem_externa:
        print("🎉 Excelente! Todas as ofertas vigentes possuem imagem interna hospedada no Storage!")
    print()

def executar_curadoria(db, bucket, opcao_modo: str, target_prod_id: str = None):
    """
    Executa a curadoria de fotos baseada no modo selecionado.
    """
    produtos_ref = db.collection("produtos")
    print("⏳ Carregando catálogo de produtos...")
    docs = list(produtos_ref.stream())
    
    produtos_pendentes = []
    for doc in docs:
        if doc.id.startswith("_"):
            continue
        d = doc.to_dict()
        url = d.get("imagem_url", "")
        origem = d.get("imagem_origem", "desconhecida")
        
        is_external_api = (origem == "api_loja" and url and "googleapis.com" not in url)
        
        incluir = False
        if opcao_modo == "1":
            # Sem imagem ou link externo de API
            incluir = (not url or is_external_api)
        elif opcao_modo == "2":
            # Apenas recortes IA
            incluir = (url and origem == "auto_crop")
        elif opcao_modo == "3":
            # Recortes aceitos e imagens externas de APIs de Lojas
            incluir = (url and (origem == "auto_crop_aceito" or is_external_api))
        elif opcao_modo == "4":
            # Tudo
            incluir = (not url or origem in ("auto_crop", "auto_crop_aceito", "padrao", "") or is_external_api)
        elif opcao_modo == "5":
            # Piloto automático (sem imagem, auto_crop ou link externo)
            incluir = (not url or origem == "auto_crop" or is_external_api)
        elif opcao_modo == "8":
            # ID específico
            incluir = (doc.id == target_prod_id)
            
        if incluir:
            produtos_pendentes.append((doc.id, d))
            
    if not produtos_pendentes:
        print("🎉 Nenhum produto pendente de curação no modo selecionado!")
        return
        
    print(f"📂 Encontrados {len(produtos_pendentes)} produtos correspondentes.")
    print("---------------------------------------------------------")
    
    total_atualizados = 0
    is_autopilot = (opcao_modo == "5")
    
    if opcao_modo == "3":
        print("\n📋 Grupo selecionado: Recortes aceitos da IA e Imagens externas de APIs de Lojas.")
        print("Como deseja prosseguir com a curadoria desse grupo?")
        print("  [1] Curar interativamente (1 por 1, escolhendo a imagem)")
        print("  [2] Rodar piloto automático (Baixar e otimizar primeira imagem encontrada automaticamente)")
        modo_exec = input("👉 Escolha a opção [1-2]: ").strip()
        if modo_exec == "2":
            is_autopilot = True
            print("\n🤖 Iniciando Piloto Automático para o Grupo 3...")
    
    for i, (prod_id, prod_data) in enumerate(produtos_pendentes):
        nome = prod_data.get("nome", "Sem nome")
        unidade = prod_data.get("unidade", "un")
        origem_atual = prod_data.get("imagem_origem", "desconhecida")
        url_atual = prod_data.get("imagem_url", "")
        
        # Busca lojas com ofertas para esse produto
        lojas = set()
        try:
            query_lojas = db.collection("ofertas").where("produto_id", "==", prod_id).stream()
            for doc_of in query_lojas:
                data_of = doc_of.to_dict()
                loja = data_of.get("loja", "")
                if loja:
                    lojas.add(loja)
        except Exception:
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
            
            # Passo 1: Busca automática de imagens no DuckDuckGo (com Fallback para Bing)
            print("   🔍 Buscando no DuckDuckGo Images...")
            urls_auto = buscar_duckduckgo_images(nome)
            fonte_busca = "DuckDuckGo"
            
            if not urls_auto:
                print("   ⚠️ Sem resultados ou bloqueio no DuckDuckGo. Tentando Bing Images...")
                urls_auto = buscar_bing_images(nome)
                fonte_busca = "Bing"
            
            if urls_auto:
                print(f"   🌐 Encontradas {len(urls_auto)} imagens no {fonte_busca}.")
                sucesso_download = False
                
                for idx, url_temp in enumerate(urls_auto):
                    print(f"     [Tentativa {idx+1}/{len(urls_auto)}] Testando: {url_temp}")
                    
                    if is_autopilot:
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
                        opcao = input(f"     👉 Usar imagem {idx+1}? [Y] Sim (Enter) / [N] Tentar próxima / [S] Pular / [A] Aceitar recorte / [M] Voltar ao Menu: ").strip().lower()
                        if opcao in ("m", "menu", "voltar"):
                            print("   🔙 Operação cancelada. Voltando ao menu principal...")
                            return
                        elif opcao == "" or opcao == "y" or opcao == "yes":
                            try:
                                buffer_otimizado = processar_e_otimizar_imagem(url_temp)
                                url_selecionada = url_temp
                                origem_selecionada = "manual"
                                successes_download = True
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
                    print(f"   ❌ Nenhuma das imagens do {fonte_busca} pós-download funcionou.")
            else:
                print("   ❌ Não encontrado no DuckDuckGo nem no Bing.")
                
            if pular_produto:
                break
                
            # Passo 2: Entrada manual caso nenhuma automática tenha sido bem-sucedida
            if not url_selecionada:
                if is_autopilot:
                    break
                opcao_manual = input("   🔗 Cole a URL ou arraste um arquivo local (ou Enter para PULAR, 'A' para aceitar recorte, 'M' para voltar ao menu): ").strip()
                if opcao_manual.lower() in ("m", "menu", "voltar"):
                    print("   🔙 Operação cancelada. Voltando ao menu principal...")
                    return
                elif opcao_manual.lower() == "a":
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

def main():
    db, bucket = inicializar_firebase()
    
    # 1. Checagem de Argumentos de Automação (Cron ou Terminal)
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--autopilot", "--piloto"):
            print("🤖 [AUTOPILOT] Iniciando Curador Automático...")
            executar_curadoria(db, bucket, "5")
        elif arg == "--sincronizar":
            executar_sincronizacao(db)
        elif arg == "--diagnostico":
            executar_diagnostico(db)
        elif arg == "--cron-completo":
            print("🤖 [CRON-COMPLETO] Iniciando Curador Automático...")
            executar_curadoria(db, bucket, "5")
            print("\n🔄 [CRON-COMPLETO] Iniciando Sincronização de Ofertas...")
            executar_sincronizacao(db)
        else:
            print(f"❌ Argumento inválido: {sys.argv[1]}")
            print("Opções válidas: --autopilot, --sincronizar, --diagnostico, --cron-completo")
        return

    # 2. Modo Interativo (Dashboard + Menu Descritivo)
    print("⏳ Carregando dados da central de imagens...")
    stats = carregar_estatisticas_gerais(db)
    
    while True:
        # Tenta limpar a tela para navegação limpa
        os.system("clear" if os.name != "nt" else "cls")
        exibir_dashboard(stats)
        
        print("SELECIONE A AÇÃO DESEJADA:\n")
        print("  [1] 🆕 Curar produtos SEM FOTO (Interativo)")
        print("      👉 Pesquisa no DuckDuckGo e pergunta antes de salvar fotos de estúdio.\n")
        print("  [2] ✂️  Curar recortes provisórios da IA [auto_crop] (Interativo)")
        print("      👉 Substitui imagens de encartes recortadas por fotos de estúdio limpas.\n")
        print("  [3] 📌 Curar recortes aceitos [auto_crop_aceito] e APIs de Lojas externas [api_loja] (Híbrido)")
        print("      👉 Permite revisar e trocar recortes aceitos ou links externos de APIs por fotos de estúdio.\n")
        print("  [4] 🔍 Varredura completa do catálogo (Interativo)")
        print("      👉 Curadoria em lote de todos os produtos (sem imagem + recortes IA).\n")
        print("  [5] 🤖 Rodar Piloto Automático (Silencioso)")
        print("      👉 Curadoria automática e em lote para produtos sem imagem ou auto_crop.\n")
        print("  [6] 🔄 Sincronizar imagens com as Ofertas")
        print("      👉 Propaga as fotos do catálogo para as ofertas vigentes no iOS App.\n")
        print("  [7] 🔎 Diagnóstico de imagens no banco de dados")
        print("      👉 Exibe estatísticas de cobertura e lista ofertas ativas sem imagem.\n")
        print("  [8] 🆔 Curar produto específico por ID")
        print("      👉 Permite digitar o ID do produto para pesquisar e atualizar a imagem dele manualmente.\n")
        print("  [0] 🚪 Sair")
        
        opcao = input("\n👉 Digite a opção desejada [0-8]: ").strip()
        
        if opcao == "0":
            print("\n👋 Saindo da Central de Imagens. Até logo!")
            break
        elif opcao in ("1", "2", "3", "4", "5", "8"):
            target_prod_id = None
            if opcao == "8":
                target_prod_id = input("\n👉 Digite o ID do produto que deseja curar: ").strip()
                if not target_prod_id:
                    print("❌ ID inválido! Operação cancelada.")
                    time.sleep(1)
                    continue
            executar_curadoria(db, bucket, opcao, target_prod_id)
            # Recarrega estatísticas após as alterações da curadoria
            print("\n⏳ Atualizando painel de estatísticas...")
            stats = carregar_estatisticas_gerais(db)
            input("\nPressione Enter para continuar...")
        elif opcao == "6":
            executar_sincronizacao(db)
            # Recarrega estatísticas para atualizar o status do app no menu
            print("\n⏳ Atualizando painel de estatísticas...")
            stats = carregar_estatisticas_gerais(db)
            input("\nPressione Enter para continuar...")
        elif opcao == "7":
            executar_diagnostico(db)
            input("\nPressione Enter para continuar...")
        else:
            print("❌ Opção inválida!")
            time.sleep(1.2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Operação cancelada pelo usuário.")
        sys.exit(0)
