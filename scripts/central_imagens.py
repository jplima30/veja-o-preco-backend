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

def buscar_google_images_playwright(nome_produto: str, page=None, max_resultados: int = 4) -> list[str]:
    """
    Busca até 4 URLs de imagens oficiais em alta resolução no Google Imagens utilizando Playwright.
    Reutiliza a página do navegador se fornecida, ou abre um contexto persistente temporário.
    """
    import re
    import urllib.parse
    
    # Limpa nome para busca
    n = nome_produto
    n = re.sub(r'\s*\((un|kg|quilo|cada|unidade|g|ml|l|pacote)\)\s*$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\s+-\s+(un|kg|quilo|cada|unidade|g|ml|l|pacote)\s*$', '', n, flags=re.IGNORECASE)
    n_limpo = re.sub(r'[-/\\_,\.]', ' ', n)
    query = ' '.join(n_limpo.split())
    
    fechar_no_fim = False
    context_temp = None
    pw_temp = None
    
    if page is None:
        try:
            from playwright.sync_api import sync_playwright
            pw_temp = sync_playwright().start()
            profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'playwright_profile'))
            context_temp = pw_temp.chromium.launch_persistent_context(
                profile_dir,
                headless=False,
                channel='chrome',
                args=['--disable-blink-features=AutomationControlled'],
                ignore_default_args=['--enable-automation'],
                locale='pt-BR'
            )
            page = context_temp.pages[0] if context_temp.pages else context_temp.new_page()
            fechar_no_fim = True
        except Exception as e_launch:
            print(f"   ⚠️ Falha ao inicializar Playwright: {e_launch}")
            return []

    urls = []
    try:
        termo_busca = f"{query} supermercado"
        
        # Se a página ainda não estiver no Google Imagens, navega para a home e acessa a aba Imagens
        if "udm=2" not in page.url and "tbm=isch" not in page.url:
            page.goto('https://www.google.com', wait_until='domcontentloaded')
            page.wait_for_timeout(800)
            q_home = page.wait_for_selector('textarea[name="q"], input[name="q"]', timeout=5000)
            q_home.fill(termo_busca)
            page.keyboard.press('Enter')
            page.wait_for_load_state('domcontentloaded')
            page.wait_for_timeout(1000)
            
            img_tab = page.query_selector('a:has-text("Imagens"), a:has-text("Images")')
            if img_tab:
                img_tab.click()
                page.wait_for_load_state('domcontentloaded')
                page.wait_for_timeout(1200)
        else:
            # Já está no Google Imagens: basta preencher o campo e dar Enter
            q_box = page.wait_for_selector('textarea[name="q"], input[name="q"]', timeout=5000)
            q_box.fill(termo_busca)
            page.keyboard.press('Enter')
            page.wait_for_load_state('domcontentloaded')
            page.wait_for_timeout(1200)
            
        cards = page.query_selector_all('div.bFtXbb img, div.uhHOwf img, img[alt]')
        candidatos = []
        for img in cards:
            try:
                alt = img.get_attribute('alt') or ''
                if any(term in alt.lower() for term in ['google', 'pesquisa', 'voos', 'mapas', 'vídeos', 'ferramentas']):
                    continue
                w = img.evaluate('el => el.naturalWidth || el.clientWidth')
                h = img.evaluate('el => el.naturalHeight || el.clientHeight')
                if w and h and (w < 40 or h < 40):
                    continue
                candidatos.append(img)
                if len(candidatos) >= max_resultados * 2:
                    break
            except Exception:
                continue
                
        for img in candidatos:
            try:
                img.click()
                page.wait_for_timeout(1000)
                
                high_res_url = page.evaluate('''() => {
                    const els = Array.from(document.querySelectorAll('img[jsname="kn3ccd"], img.sFlh5c[src^="http"]'));
                    for (const el of els) {
                        const s = el.src || '';
                        if (s.startsWith('http') && !s.includes('gstatic.com') && !s.includes('google.com')) {
                            return s;
                        }
                    }
                    return '';
                }''')
                
                if high_res_url and high_res_url not in urls:
                    banned = ['wikipedia', 'wikimedia', 'noticia', 'g1.globo', 'facebook', 'instagram', 'paintingvalley', 'inuth.com']
                    if not any(b in high_res_url.lower() for b in banned):
                        urls.append(high_res_url)
                        if len(urls) >= max_resultados:
                            break
            except Exception:
                pass
                
    except Exception as e_search:
        print(f"   ⚠️ Erro ao consultar Google Imagens: {e_search}")
    finally:
        if fechar_no_fim:
            try:
                if context_temp: context_temp.close()
                if pw_temp: pw_temp.stop()
            except Exception:
                pass

                
    return urls

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

def processar_e_otimizar_imagem(url_imagem: str, tamanho: tuple = (400, 400), qualidade: int = 80) -> io.BytesIO:
    """
    Baixa uma imagem da internet ou abre um arquivo local do disco,
    ajusta sua proporção com preenchimento branco (400x400) e comprime para JPEG 80%.
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
        resp = requests.get(url_limpa, headers=headers, timeout=12)
        resp.raise_for_status()
        img_bytes = io.BytesIO(resp.content)
        
    with Image.open(img_bytes) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Redimensionamento 400x400 preservando proporção com fundo branco
        img_redimensionada = ImageOps.pad(img, tamanho, color="white", centering=(0.5, 0.5))
        
        output = io.BytesIO()
        img_redimensionada.save(output, "JPEG", quality=qualidade, optimize=True)
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
    if opcao_modo == "8" and target_prod_id:
        # Tenta buscar na coleção de ofertas primeiro caso o ID seja de uma oferta
        try:
            offer_doc = db.collection("ofertas").document(target_prod_id).get()
            if offer_doc.exists:
                offer_data = offer_doc.to_dict()
                resolved_prod_id = offer_data.get("produto_id")
                if resolved_prod_id:
                    print(f"\n📌 ID digitado corresponde à oferta: '{offer_data.get('produto_nome')}'")
                    print(f"   👉 Resolvido para o ID do produto correspondente: '{resolved_prod_id}'\n")
                    target_prod_id = resolved_prod_id
        except Exception as e_res:
            print(f"⚠️ Erro ao verificar se ID é de oferta: {e_res}")
            
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
    
    # Inicia instância do Playwright com perfil persistente para evitar CAPTCHA e reutilizar na varredura
    pw = None
    context = None
    page = None
    try:
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
    except Exception as e_pw:
        print(f"⚠️ Aviso: Falha ao iniciar navegador Playwright persistente: {e_pw}")

    try:
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
                
                # Passo 1: Busca automática de imagens no Google Imagens (Playwright)
                print("   🔍 Buscando no Google Imagens (Playwright)...")
                urls_auto = buscar_google_images_playwright(nome, page=page)
                fonte_busca = "Google Imagens"
                
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
                                print("     🤖 [AUTO-PILOTO] Imagem baixada e otimizada (400x400) com sucesso.")
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
                    print("   ❌ Nenhuma imagem comercial encontrada no Google Imagens.")
                    
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
                        
                # Passo 3: Fazer Upload dos dados (o buffer_otimizado já está preenchido em 400x400)
                try:
                    print("   ☁️ Fazendo upload para o Firebase Storage...")
                    blob_name = f"produtos/{prod_id}.jpg"
                    blob = bucket.blob(blob_name)
                    blob.upload_from_string(buffer_otimizado.getvalue(), content_type="image/jpeg")
                    blob.make_public()
                    timestamp_agora = int(time.time())
                    public_url = f"{blob.public_url}?t={timestamp_agora}"
                    
                    print("   💾 Salvando metadados no Firestore...")
                    ref_doc = produtos_ref.document(prod_id)
                    ref_doc.update({
                        "imagem_url": public_url,
                        "imagem_origem": origem_selecionada,
                        "atualizado_em": datetime.now()
                    })
                    
                    tamanho_kb = len(buffer_otimizado.getvalue()) / 1024.0
                    print(f"   ✅ SUCESSO! Imagem curada (400x400) salva com sucesso ({tamanho_kb:.2f} KB)!")
                    total_atualizados += 1
                    break
                    
                except Exception as e_up:
                    print(f"   ❌ ERRO ao fazer upload ou salvar Firestore: {e_up}")
                    break
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        if pw:
            try:
                pw.stop()
            except Exception:
                pass


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
        print("      👉 Pesquisa no Google Imagens (Playwright) e pergunta antes de salvar fotos de estúdio (400x400).\n")
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
