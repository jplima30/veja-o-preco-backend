import os
import sys
import time
import requests
import json
import base64
import shutil
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "playwright_profile")
ENDPOINT_FIREBASE = "https://extrair-dados-imagem-kcglywisya-uc.a.run.app"
HISTORICO_ARQUIVO = os.path.join(os.path.dirname(__file__), "historico_posts.json")
MODO_AUDITORIA_VISUAL = True  # MODO AUDITORIA: Salva imagens localmente para triagem posterior via OCR
JANELAS_HORARIO = [10, 14]  # Horários permitidos para varredura automática (10h e 14h)

def gerenciar_auditoria_visual(janela=None):
    base_dir = os.path.join(os.path.dirname(__file__), "..", "auditoria_visual")
    hoje = datetime.now()
    dias_semana = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
    nome_dia = dias_semana[hoje.weekday()]
    
    pasta_data_nome = f"{hoje.strftime('%Y-%m-%d')}_{nome_dia}"
    caminho_dia = os.path.join(base_dir, pasta_data_nome)
    
    # Se não houver janela, assume 'manual' para evitar pastas órfãs
    if not janela:
        janela = "manual"
        
    # Só adiciona 'h' se for um número (janela de horário)
    subpasta = f"{janela}h" if str(janela).isdigit() else str(janela)
    caminho_final = os.path.join(caminho_dia, subpasta)
    
    os.makedirs(caminho_final, exist_ok=True)
    return caminho_final

# Inicialmente None, será definido no main
PASTA_AUDITORIA_HOJE = None

def carregar_historico():
    if os.path.exists(HISTORICO_ARQUIVO):
        try:
            with open(HISTORICO_ARQUIVO, "r") as f:
                return json.load(f)
        except: pass
    return {}

def salvar_historico(historico):
    with open(HISTORICO_ARQUIVO, "w") as f:
        json.dump(historico, f, indent=4)

def verificar_permissao_execucao(historico):
    agora = datetime.now()
    hoje_str = agora.strftime("%Y-%m-%d")
    
    # Estrutura: "controle_execucao": {"janelas_concluidas": {"2026-04-28": ["10", "14"]}}
    controle = historico.get("controle_execucao", {"janelas_concluidas": {}})
    if "janelas_concluidas" not in controle: # Migração/Correção
        controle = {"janelas_concluidas": {}}
        
    janelas_hoje = controle["janelas_concluidas"].get(hoje_str, [])
    
    # Identifica a janela mais recente que já deveria ter ocorrido
    janela_atual = None
    for h in sorted(JANELAS_HORARIO):
        if agora.hour >= h:
            janela_atual = h
            
    if janela_atual is None:
        print(f"⏳ [AGUARDANDO] Fora de horário. Próxima varredura às {min(JANELAS_HORARIO)}h.")
        return False, None

    if str(janela_atual) in janelas_hoje:
        print(f"✅ [CONCLUÍDO] A varredura de {janela_atual}h já foi realizada hoje ({hoje_str}).")
        return False, None
        
    print(f"🚀 [EXECUTANDO] Iniciando captura para a janela de {janela_atual}h...")
    return True, janela_atual

def registrar_sucesso_janela(historico, janela):
    hoje_str = datetime.now().strftime("%Y-%m-%d")
    controle = historico.get("controle_execucao", {"janelas_concluidas": {}})
    
    if hoje_str not in controle["janelas_concluidas"]:
        controle["janelas_concluidas"][hoje_str] = []
        
    if str(janela) not in controle["janelas_concluidas"][hoje_str]:
        controle["janelas_concluidas"][hoje_str].append(str(janela))
        
    historico["controle_execucao"] = controle
    salvar_historico(historico)

ALVOS = [
    {"username": "supermercadoslider", "supermercado_id": "lider-am"},
    {"username": "formosaoficial", "supermercado_id": "formosa-am"},
    {"username": "mmguerreirao", "supermercado_id": "guerreirao-br"},
    {"username": "assaiatacadistaoficial", "supermercado_id": "assai-am"}
]

def processar_assai_site(page, historico):
    print("\n🌐 [MÉTODO SITE] Iniciando busca no site oficial do Assaí...")
    url_loja = "https://www.assai.com.br/ofertas/para/assai-augusto-montenegro"
    
    try:
        print(f"  🛰️ Navegando para: {url_loja}")
        page.goto(url_loja, timeout=60000)
        page.wait_for_load_state("networkidle")
        
        print("  📜 Rolando e interagindo com o carrossel para revelar todos os encartes...")
        page.evaluate("window.scrollTo(0, 500)") # Rola até onde os encartes costumam estar
        time.sleep(2)
        
        # Tenta clicar em setas ou bolinhas do carrossel se existirem
        try:
            dots = page.locator(".slick-dots li button")
            count = dots.count()
            if count > 0:
                print(f"    🖱️ Detectadas {count} opções no carrossel. Clicando em todas...")
                for j in range(count):
                    dots.nth(j).click()
                    time.sleep(1)
        except: pass

        # Tentar extrair TODOS os IDs únicos
        print("  🔍 Vasculhando o HTML em busca de TODOS os encartes ativos...")
        
        pares_unicos = []
        def extrair_pares(html_content):
            # Regex ultra-flexível para pegar qualquer link de imagem do encarte
            encontrados = re.findall(r'cloudfront\.net/RPA/v3/(\d+)/campanha-(\d+)-cluster-(\d+)', html_content)
            for c_pasta, c_arq, cluster in encontrados:
                par = (c_pasta, cluster)
                if par not in pares_unicos:
                    pares_unicos.append(par)
                    print(f"    ✨ Encarte detectado: Campanha {c_pasta}, Cluster {cluster}")

        # Captura inicial
        extrair_pares(page.content())

        # --- Interagir com as ABAS (Tabs) reais do Assaí ---
        try:
            # O seletor real descoberto é '.ofertas-tab button'
            tabs = page.locator(".ofertas-tab button")
            tab_count = tabs.count()
            if tab_count > 1:
                print(f"    📂 Detectadas {tab_count} abas de categorias (Jornais de Ofertas).")
                for t in range(tab_count):
                    try:
                        # Pega o texto da aba para o log
                        tab_text = tabs.nth(t).inner_text() or f"Aba {t+1}"
                        print(f"      📑 Clicando na: {tab_text}...")
                        tabs.nth(t).click(timeout=5000)
                        time.sleep(3) # Aguarda o carrossel trocar
                        
                        # Extrai os pares dessa aba
                        extrair_pares(page.content())
                        
                        # Tenta girar um pouco o carrossel interno
                        dots = page.locator(".slick-dots li button, .slick-next")
                        for d in range(min(dots.count(), 3)):
                            try:
                                dots.nth(d).click(timeout=1000)
                                time.sleep(1)
                                extrair_pares(page.content())
                            except: pass
                    except Exception as e_tab:
                        print(f"      ⚠️ Erro ao clicar na aba {t}: {e_tab}")
        except Exception as e_tabs_main:
            print(f"    ⚠️ Erro geral nas abas: {e_tabs_main}")

        # Tenta o carrossel geral caso não tenha abas ou como segurança extra
        try:
            dots = page.locator(".slick-dots li button, .slick-next, .slick-prev")
            count = dots.count()
            if count > 0:
                print(f"    🎡 Verificação final no carrossel principal...")
                for j in range(min(count, 5)):
                    try:
                        dots.nth(j).click(timeout=2000)
                        time.sleep(1.5)
                        extrair_pares(page.content())
                    except: pass
        except: pass

        if not pares_unicos:
            print("  ❌ Nenhum encarte encontrado.")
            return

        print(f"  📚 Total de encartes ÚNICOS detectados no site: {len(pares_unicos)}")

        algum_novo = False
        for campanha, cluster in pares_unicos:
            id_chave = f"site-assai-{campanha}-{cluster}"
            
            historico_assai = historico.get("assai_site", {})
            if id_chave in historico_assai:
                print(f"  ⏭️ Encarte {id_chave} já processado anteriormente. Pulando...")
                continue

            algum_novo = True
            print(f"  🔥 Processando Encarte NOVO: Campanha {campanha}, Cluster {cluster}")
            
            # Baixar imagens localmente
            frames_b64 = []
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": "https://www.assai.com.br/"
            }

            for i in range(1, 11):
                img_url = f"https://d2q57q7k4hzryv.cloudfront.net/RPA/v3/{campanha}/campanha-{campanha}-cluster-{cluster}-pagina-{i}.jpeg"
                try:
                    resp = requests.get(img_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        print(f"    📸 Página {i} capturada.")
                        frames_b64.append(base64.b64encode(resp.content).decode('utf-8'))
                        
                        # Auditoria
                        pasta_audit = os.path.join(PASTA_AUDITORIA_HOJE, "assai_site", id_chave)
                        os.makedirs(pasta_audit, exist_ok=True)
                        with open(os.path.join(pasta_audit, f"pagina_{i}.jpg"), "wb") as f:
                            f.write(resp.content)
                    else:
                        break # Fim das páginas deste encarte
                except:
                    break

            if frames_b64:
                if MODO_AUDITORIA_VISUAL:
                    print(f"  📦 [Modo auditoria] Encarte {cluster} salvo localmente para análise.")
                    # No modo auditoria, ainda salvamos no histórico local para não baixar de novo
                    historico_assai[id_chave] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    historico["assai_site"] = historico_assai
                    salvar_historico(historico)
                else:
                    print(f"  🚀 Enviando {len(frames_b64)} páginas (Encarte {cluster}) para o Gemini...")
                    payload = {
                        "supermercado_id": "assai",
                        "frames_b64": frames_b64,
                        "senha": "senha_segura_123"
                    }
                    resposta = requests.post(ENDPOINT_FIREBASE, json=payload)
                    if resposta.status_code == 200:
                        print(f"  ✅ Encarte {cluster} salvo com sucesso!")
                        historico_assai[id_chave] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        historico["assai_site"] = historico_assai
                        salvar_historico(historico)
                    else:
                        print(f"  ❌ Erro no Firebase: {resposta.text}")
        
        if not algum_novo and pares_unicos:
            print("  ❌ Não há novos encartes para processar.")

    except Exception as e:
        print(f"  ❌ Erro crítico ao processar site do Assaí: {e}")

def processar_instagram(page, historico):
    for alvo in ALVOS:
        print(f"\n🔍 Acessando perfil do Instagram: @{alvo['username']}...")
        
        media_capturada = []
        def handle_response(response):
            try:
                url = response.url
                ctype = response.headers.get("content-type", "")
                if ("image/" in ctype or ".jpg" in url or ".webp" in url) and ("cdninstagram" in url or "fbcdn" in url or "scontent" in url):
                    if "150x150" not in url and "320x320" not in url and "-19/" not in url:
                        media_capturada.append({"tipo": "imagem", "url": url})
            except: pass

        page.on("response", handle_response)
        
        try:
            page.goto(f"https://www.instagram.com/{alvo['username']}/", timeout=60000)
            print(f"  ⏳ Aguardando carregamento da grade de posts...")
            time.sleep(5)
            
            links = page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')
            if not links:
                print(f"  ⚠️ Nenhum post visível para @{alvo['username']}.")
                continue
                
            historico_loja = historico.get(alvo['username'], {})
            if isinstance(historico_loja, list): # Migração se necessário
                historico_loja = {url: "Antigo" for url in historico_loja}
            
            posts_novos_count = 0
            for link in links[:15]:
                href = link.get_attribute("href")
                if href in historico_loja:
                    print(f"  ⏭️ Post {href} já processado anteriormente. Pulando...")
                    continue

                print(f"  ✨ NOVIDADE! Post novo encontrado: {href}")
                posts_novos_count += 1
                media_capturada.clear()
                
                print("  🖱️ Clicando no post para abrir o modal...")
                link.click()
                time.sleep(5) # Espera carregar vídeo/fotos
                
                video_count = page.locator("video").count()
                frames_b64 = []
                midia_final = None

                if video_count > 0:
                    print("  🎥 VÍDEO detectado! Extraindo frames para auditoria visual...")
                    try:
                        duration = page.evaluate('() => document.querySelector("video")?.duration || 15')
                        step = max(2, int(duration / 15))
                        for t in range(0, int(duration), step):
                            page.evaluate(f'() => document.querySelector("video").currentTime = {t}')
                            time.sleep(1.5)
                            img_bytes = page.locator("video").first.screenshot(type="jpeg", quality=75)
                            frames_b64.append(base64.b64encode(img_bytes).decode('utf-8'))
                            print(f"    📸 Frame capturado: {t}s")
                            
                            # Auditoria
                            post_id = href.strip("/").split("/")[-1]
                            pasta_audit = os.path.join(PASTA_AUDITORIA_HOJE, alvo['username'], post_id)
                            os.makedirs(pasta_audit, exist_ok=True)
                            with open(os.path.join(pasta_audit, f"frame_{t}s.jpg"), "wb") as f:
                                f.write(img_bytes)
                    except Exception as e:
                        print(f"    ❌ Erro ao extrair frames: {e}")
                else:
                    if media_capturada:
                        midia_final = media_capturada[-1]["url"]
                        print(f"  🖼️ IMAGEM estática detectada. URL: {midia_final[:50]}...")
                        
                        # Auditoria
                        try:
                            post_id = href.strip("/").split("/")[-1]
                            pasta_audit = os.path.join(PASTA_AUDITORIA_HOJE, alvo['username'], post_id)
                            os.makedirs(pasta_audit, exist_ok=True)
                            img_resp = requests.get(midia_final, timeout=10)
                            with open(os.path.join(pasta_audit, "imagem_original.jpg"), "wb") as f:
                                f.write(img_resp.content)
                        except: pass

                if midia_final or frames_b64:
                    if MODO_AUDITORIA_VISUAL:
                        print(f"  📦 [Modo auditoria] Post {href} salvo localmente para análise.")
                        historico_loja[href] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        historico[alvo['username']] = historico_loja
                        salvar_historico(historico)
                    else:
                        print(f"  🚀 Enviando para o Firebase (Supermercado: {alvo['supermercado_id']})...")
                        payload = {
                            "supermercado_id": alvo["supermercado_id"],
                            "frames_b64": frames_b64 if frames_b64 else None,
                            "url": midia_final if not frames_b64 else None,
                            "senha": "senha_segura_123"
                        }
                        resp = requests.post(ENDPOINT_FIREBASE, json=payload)
                        if resp.status_code == 200:
                            print(f"  ✅ SUCESSO! Dados do post {href} enviados e processados.")
                            historico_loja[href] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                            historico[alvo['username']] = historico_loja
                            salvar_historico(historico)
                        else:
                            print(f"  ❌ Erro no Firebase: {resp.status_code} - {resp.text}")

                print("  ⌨️ Fechando o post (Esc)...")
                page.keyboard.press("Escape")
                time.sleep(2)
            
            if posts_novos_count == 0:
                print(f"  ✅ Não há novos posts em @{alvo['username']}.")
                
        except Exception as e:
            print(f"  ❌ Erro fatal ao processar @{alvo['username']}: {e}")

if __name__ == "__main__":
    print("=========================================================")
    print("🤖 INICIANDO AUTOMAÇÃO DE EXTRAÇÃO - PLAYWRIGHT")
    print("   (Auditoria Visual e Coleta de Encartes)")
    print("=========================================================")
    
    historico = carregar_historico()
    
    force = "--force" in sys.argv
    permissao, janela_alvo = verificar_permissao_execucao(historico)
    
    if force:
        print("⚠️ [MODO FORÇADO] Ignorando janelas de horário para execução manual.")
        janela_alvo = janela_alvo or "manual"
    elif not permissao:
        print("=========================================================")
        print("🏁 ENCERRANDO: Fora do horário ou já executado.")
        print("   (Dica: use --force para rodar manualmente agora)")
        print("=========================================================")
        exit(0)

    # Define a pasta de auditoria específica para esta janela
    PASTA_AUDITORIA_HOJE = gerenciar_auditoria_visual(janela_alvo)
    
    # Extrai apenas o nome final da pasta para o log
    nome_janela_log = os.path.basename(PASTA_AUDITORIA_HOJE)
    print(f"📂 [ARQUIVOS] Fotos desta sessão serão salvas em: {nome_janela_log}")

    with sync_playwright() as p:
        # Abrindo o navegador (headless=False para você ver ele trabalhando!)
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR, 
            headless=False
        )
        page = browser.new_page()

        # 1. Primeiro: Atacar o site do Assaí (Ignora bloqueios de datacenter)
        processar_assai_site(page, historico)

        # 2. Segundo: Varredura nos perfis do Instagram
        processar_instagram(page, historico)
        
        browser.close()
    
    # Registrar que esta janela foi concluída com sucesso
    registrar_sucesso_janela(historico, janela_alvo)

    print("\n" + "="*60)
    print("🚀 [PRÓXIMO PASSO] Iniciando Triagem Automatizada...")
    print("="*60)
    
    import subprocess
    # Caminho absoluto para o Python do venv de triagem
    venv_python = os.path.join(os.path.dirname(__file__), "..", "venv_triagem", "bin", "python3")
    script_triagem = os.path.join(os.path.dirname(__file__), "triagem_automatizada.py")
    
    try:
        print(f"  🧠 Rodando triagem [{janela_alvo}h] com: {venv_python}")
        # Passa a janela como argumento para a triagem
        subprocess.run([venv_python, script_triagem, str(janela_alvo)], check=True)
    except Exception as e:
        print(f"⚠️ Erro ao iniciar triagem automática: {e}")
    
    print("\n=========================================================")
    print("🏁 CRON LOCAL FINALIZADO COM SUCESSO!")
    print("=========================================================")
