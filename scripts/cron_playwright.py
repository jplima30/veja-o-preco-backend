import os
os.environ["PW_TEST_SCREENSHOT_NO_FONTS_READY"] = "1"
import sys

# Garante que a saída seja impressa em tempo real no terminal/cron
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

import time
import requests
import json
import base64
import shutil
import re
import subprocess
import glob
from datetime import datetime
from playwright.sync_api import sync_playwright
import random

try:
    import fitz # PyMuPDF para extração precisa de páginas
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

USER_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "playwright_profile"))
ENDPOINT_FIREBASE = "https://extrair-dados-imagem-kcglywisya-uc.a.run.app"
ENDPOINT_PDF = "https://extrair-dados-encarte-kcglywisya-uc.a.run.app"
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

def processar_assai_site(page, historico, force=False):
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
            if id_chave in historico_assai and not force:
                print(f"  ⏭️ Encarte {id_chave} já processado anteriormente. Pulando...")
                continue

            if force:
                print(f"  🔄 [FORCE] Ignorando histórico e limpando pasta para: {id_chave}")

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
                        if force and os.path.exists(pasta_audit):
                            shutil.rmtree(pasta_audit)
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

def processar_mateus_site(page, historico, force=False):
    print("\n🛒 [MÉTODO SITE] Iniciando busca no site oficial do Mateus...")
    url_mateus = "https://ofertasmateus.com/pa/ananindeua/mateus-jaderlandia"
    
    try:
        print(f"  🛰️ Navegando para: {url_mateus}")
        page.goto(url_mateus, timeout=60000)
        page.wait_for_load_state("networkidle")
        
        # O site do Mateus carrega os encartes em uma grade
        print("  🔍 Localizando encartes na página...")
        try:
            page.wait_for_selector(".encarte-item", timeout=10000)
        except:
            print("  ⚠️ Encartes não apareceram. Tentando clicar em 'Escolha o Encarte'...")
            try:
                page.click("text=Escolha o Encarte", timeout=5000)
                page.wait_for_selector(".encarte-item", timeout=10000)
            except: pass

        encartes = page.locator(".encarte-item")
        count = encartes.count()
        
        if count == 0:
            print("  ⚠️ Nenhum encarte encontrado na página do Mateus.")
            return

        print(f"  📚 Encontrados {count} encartes. Verificando novidades...")
        
        historico_mateus = historico.get("mateus_site", {})
        algum_novo = False

        for i in range(count):
            try:
                item = encartes.nth(i)
                titulo = item.locator(".encarte-nome").inner_text().strip()
                
                # [MELHORIA] Ignorar botão de fechar "Escolha o Encarte" que o site renderiza como item
                if "Escolha o Encarte" in titulo:
                    continue

                print(f"  🔍 Verificando encarte: {titulo}")

                # Clicar para abrir o modal e pegar o link do PDF
                item.locator(".encarte-item-ver-btn").click()
                page.wait_for_selector("a[title='Baixar encarte']", timeout=10000)
                
                link_pdf = page.locator("a[title='Baixar encarte']").get_attribute("href")
                
                if not link_pdf:
                    print(f"  ⚠️ Não foi possível obter o link do PDF para '{titulo}'.")
                    page.keyboard.press("Escape")
                    continue

                if not link_pdf.startswith("http"):
                    link_pdf = "https://ofertasmateus.com" + link_pdf

                # [MELHORIA] ID Chave baseado na URL do PDF para evitar duplicatas com nomes iguais (ex: "Folheto")
                # Se o link for genérico (como api-proxy.php), usamos um hash do link completo
                parsed_filename = link_pdf.split("/")[-1].split("?")[0].replace(".pdf", "")
                if "proxy" in parsed_filename or len(parsed_filename) < 3:
                    import hashlib
                    id_pasta = hashlib.md5(link_pdf.encode()).hexdigest()[:10]
                else:
                    id_pasta = parsed_filename
                
                id_chave = f"mateus-{id_pasta}"

                if id_chave in historico_mateus and not force:
                    print(f"  ⏭️ Encarte '{titulo}' (ID: {id_pasta}) já processado. Pulando...")
                    page.keyboard.press("Escape")
                    continue
                
                if force:
                    print(f"  🔄 [FORCE] Forçando re-processamento do encarte: {titulo}")
                    # [LIMPEZA AGRESSIVA] No modo force, limpamos tudo do encarte específico
                    pasta_mateus = os.path.join(PASTA_AUDITORIA_HOJE, "mateus_site")
                    pasta_paginas = os.path.join(pasta_mateus, id_pasta)
                    caminho_pdf_antigo = os.path.join(pasta_mateus, f"mateus_site_{id_pasta}.pdf")
                    
                    if os.path.exists(pasta_paginas):
                        print(f"    🧹 [FORCE] Removendo pasta de imagens anterior: {id_pasta}")
                        shutil.rmtree(pasta_paginas)
                    if os.path.exists(caminho_pdf_antigo):
                        print(f"    🧹 [FORCE] Removendo PDF anterior.")
                        os.remove(caminho_pdf_antigo)

                print(f"  🔥 NOVO ENCARTE: {titulo} (ID: {id_pasta})")
                algum_novo = True

                print(f"  🔗 Link capturado: {link_pdf}")

                # No modo auditoria, baixamos o arquivo localmente
                if MODO_AUDITORIA_VISUAL:
                    print(f"  📥 Baixando PDF para auditoria local...")
                    try:
                        resp_pdf = page.request.get(link_pdf)
                        if resp_pdf.status == 200:
                            pasta_mateus = os.path.join(PASTA_AUDITORIA_HOJE, "mateus_site")
                            os.makedirs(pasta_mateus, exist_ok=True)
                            
                            # ID curto para pasta e arquivos
                            nome_base = f"mateus_site_{id_pasta}"
                            
                            caminho_pdf = os.path.join(pasta_mateus, f"{nome_base}.pdf")
                            
                            with open(caminho_pdf, "wb") as f:
                                f.write(resp_pdf.body())
                            
                            print(f"  ✅ PDF baixado: {nome_base}.pdf ({len(resp_pdf.body())} bytes)")

                            # CAPTURA DE PÁGINAS (Preferencialmente via PyMuPDF para precisão de 1 imagem/página)
                            print(f"  📸 Processando páginas do PDF...")
                            try:
                                pasta_paginas = os.path.join(pasta_mateus, id_pasta)
                                if force and os.path.exists(pasta_paginas):
                                    print(f"    🧹 [FORCE] Limpando pasta anterior: {id_pasta}")
                                    shutil.rmtree(pasta_paginas)
                                os.makedirs(pasta_paginas, exist_ok=True)
                                
                                if FITZ_AVAILABLE:
                                    print("    ⚙️ Usando PyMuPDF para extração de alta precisão...")
                                    doc = fitz.open(caminho_pdf)
                                    total_paginas = len(doc)
                                    print(f"    📄 PDF detectado com {total_paginas} páginas.")
                                    
                                    for i in range(total_paginas):
                                        caminho_jpg = os.path.join(pasta_paginas, f"pagina_{i+1}.jpg")
                                        page_obj = doc.load_page(i)
                                        # Matrix(2, 2) aumenta a resolução (DPI) para 144 (72*2) para melhor OCR
                                        pix = page_obj.get_pixmap(matrix=fitz.Matrix(2, 2))
                                        pix.save(caminho_jpg)
                                        print(f"    ✅ Página {i+1}/{total_paginas} extraída.")
                                    doc.close()
                                else:
                                    print("    ⚠️ PyMuPDF não disponível. Usando fallback via Navegador (menos preciso)...")
                                    pdf_page = page.context.new_page()
                                    pdf_page.set_viewport_size({"width": 1280, "height": 1600})
                                    abs_pdf_path = os.path.abspath(caminho_pdf)
                                    pdf_page.goto(f"file://{abs_pdf_path}")
                                    pdf_page.wait_for_timeout(5000)
                                    pdf_page.mouse.click(640, 800)
                                    
                                    for j in range(1, 15):
                                        caminho_img = os.path.join(pasta_paginas, f"pagina_{j}.png")
                                        pdf_page.screenshot(path=caminho_img)
                                        pdf_page.keyboard.press("PageDown")
                                        pdf_page.wait_for_timeout(1500)
                                        # [MELHORIA] Se não tem PyMuPDF, pelo menos limpamos o sips depois
                                    pdf_page.close()
                                
                                # [OTIMIZAÇÃO] Se usamos o fallback (png), convertemos. Se usamos fitz (jpg), apenas logamos.
                                if not FITZ_AVAILABLE:
                                    print(f"    🪄 Otimizando imagens PNG para JPG...")
                                    for png_file in glob.glob(os.path.join(pasta_paginas, "*.png")):
                                        nome_sem_ext = os.path.splitext(png_file)[0]
                                        caminho_jpg = f"{nome_sem_ext}.jpg"
                                        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "70", "-Z", "1200", png_file, "--out", caminho_jpg], capture_output=True)
                                        if os.path.exists(caminho_jpg): os.remove(png_file)
                                
                                print(f"  ✅  Imagens geradas em: {id_pasta}/")
                            except Exception as e_conv:
                                print(f"  ⚠️ Erro na captura via browser: {e_conv}")
                            
                            historico_mateus[id_chave] = {
                                "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                "url": link_pdf,
                                "arquivo_local": caminho_pdf
                            }
                        else:
                            print(f"  ❌ Erro ao baixar PDF (Status: {resp_pdf.status})")
                    except Exception as e_down:
                        print(f"  ❌ Falha no download do PDF: {e_down}")
                else:
                    print(f"  🚀 Enviando link para o Cérebro Gemini (PDF)...")
                    payload = {
                        "url": link_pdf,
                        "supermercado_id": "mateus-jaderlandia",
                        "loja": "Mix Mateus (Jaderlândia)"
                    }
                    resposta = requests.post(ENDPOINT_PDF, json=payload, timeout=120)
                    
                    if resposta.status_code == 200:
                        print(f"  ✅ Encarte '{titulo}' processado com sucesso!")
                        historico_mateus[id_chave] = {
                            "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                            "url": link_pdf
                        }
                    else:
                        print(f"  ❌ Erro no Firebase: {resposta.text}")

                # Fecha o modal
                page.keyboard.press("Escape")
                time.sleep(1)

            except Exception as e_item:
                print(f"  ⚠️ Erro ao processar item {i} do Mateus: {e_item}")
                page.keyboard.press("Escape")

        if algum_novo:
            historico["mateus_site"] = historico_mateus
            salvar_historico(historico)
        else:
            print("  ✅ Tudo atualizado no Mateus.")

    except Exception as e:
        print(f"  ❌ Erro crítico ao processar site do Mateus: {e}")

def processar_instagram(page, historico, force=False):
    print("\n🌡️ [AQUECIMENTO] Acessando a página inicial do Instagram primeiro para gerar cookies/sessão naturais...")
    try:
        page.goto("https://www.instagram.com/", timeout=60000)
        time.sleep(random.uniform(3.0, 5.0))
        page.mouse.move(random.randint(100, 500), random.randint(100, 500))
        page.mouse.wheel(0, random.randint(300, 800))
        time.sleep(random.uniform(2.0, 4.0))
    except Exception as e:
        print(f"⚠️ Erro no aquecimento: {e}")

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
            # Simula um pequeno atraso humano antes de digitar a URL
            time.sleep(random.uniform(1.5, 3.5))
            page.goto(f"https://www.instagram.com/{alvo['username']}/", timeout=60000)
            print(f"  ⏳ Aguardando carregamento da grade de posts (Modo Humano)...")
            
            # Movimento errático de mouse antes de esperar
            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            time.sleep(random.uniform(4.0, 6.5))
            
            # Rola a tela levemente como um humano visualizando o feed
            page.mouse.wheel(0, random.randint(300, 800))
            time.sleep(random.uniform(1.5, 3.0))
            
            # [MELHORIA] Verificação de Login - Se o Instagram pedir login, pausamos para o usuário
            # Usamos .first para evitar strict mode violation se houver mais de um botão "Entrar"
            if "login" in page.url.lower() or page.locator("text=Entrar").first.is_visible():
                print("\n" + "!"*60)
                print("🔑 [AÇÃO REQUERIDA] O INSTAGRAM PEDIU LOGIN!")
                print("   Como o navegador está VISÍVEL, por favor faça o login manualmente.")
                print("   O script vai aguardar 30 segundos ou você pode pressionar ENTER aqui.")
                print("!"*60 + "\n")
                # Tenta esperar interação ou timeout
                try:
                    # Pequeno truque para esperar o usuário sem travar totalmente se for automático
                    for _ in range(30):
                        if not ("login" in page.url.lower()): break
                        time.sleep(1)
                except: pass
            
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
                if href in historico_loja and not force:
                    print(f"  ⏭️ Post {href} já processado anteriormente. Pulando...")
                    continue

                if force:
                    print(f"  🔄 [FORCE] Forçando re-processamento do post: {href}")

                print(f"  ✨ NOVIDADE! Post novo encontrado: {href}")
                posts_novos_count += 1
                media_capturada.clear()
                
                print("  🖱️ Aproximando o mouse e clicando no post...")
                # Hover antes de clicar (Ação comum humana)
                link.hover()
                time.sleep(random.uniform(0.5, 1.5))
                link.click()
                time.sleep(random.uniform(4.5, 7.0)) # Espera carregar vídeo/fotos de forma natural
                
                video_count = page.locator("video").count()
                frames_b64 = []
                midia_final = None

                if video_count > 0:
                    print("  🎥 VÍDEO detectado! Extraindo frames para auditoria visual...")
                    
                    # [FIX] Forçar reprodução do vídeo — Instagram inicia Reels pausados no modal
                    try:
                        page.evaluate('() => { const v = document.querySelector("video"); if(v) { v.muted = true; v.play(); } }')
                        page.wait_for_function(
                            '() => { const v = document.querySelector("video"); return v && v.readyState >= 2; }',
                            timeout=8000
                        )
                        print("    ▶️ Vídeo reproduzindo com sucesso.")
                    except Exception as e_play:
                        print(f"    ⚠️ Não foi possível iniciar reprodução do vídeo: {e_play}")
                    
                    # [FIX] Captura de frames com try/except individual (resiliência)
                    try:
                        duration = page.evaluate('() => document.querySelector("video")?.duration || 15')
                        step = max(2, int(duration / 15))
                        falhas_consecutivas = 0
                        
                        for t in range(0, int(duration), step):
                            try:
                                page.evaluate(f'() => document.querySelector("video").currentTime = {t}')
                                time.sleep(1.5)
                                video_element = page.locator("video").first
                                if video_element.is_visible():
                                    img_bytes = video_element.screenshot(type="jpeg", quality=75, timeout=15000)
                                else:
                                    box = video_element.bounding_box()
                                    if box:
                                        img_bytes = page.screenshot(type="jpeg", quality=75, clip=box, timeout=15000)
                                    else:
                                        img_bytes = page.screenshot(type="jpeg", quality=75, timeout=15000)
                                frames_b64.append(base64.b64encode(img_bytes).decode('utf-8'))
                                print(f"    📸 Frame capturado: {t}s")
                                falhas_consecutivas = 0
                                
                                # Auditoria
                                post_id = href.strip("/").split("/")[-1]
                                pasta_audit = os.path.join(PASTA_AUDITORIA_HOJE, alvo['username'], post_id)
                                os.makedirs(pasta_audit, exist_ok=True)
                                with open(os.path.join(pasta_audit, f"frame_{t}s.jpg"), "wb") as f:
                                    f.write(img_bytes)
                            except Exception as e_frame:
                                falhas_consecutivas += 1
                                print(f"    ⚠️ Frame {t}s falhou ({falhas_consecutivas}x): {e_frame}")
                                if falhas_consecutivas >= 3:
                                    print(f"    🛑 3 falhas consecutivas — abortando captura de frames deste vídeo.")
                                    break
                    except Exception as e:
                        print(f"    ❌ Erro ao configurar captura de frames: {e}")
                    
                    # [FIX] Fallback: se nenhum frame foi capturado, tentar poster/thumbnail do vídeo
                    if not frames_b64:
                        print("    🔄 Nenhum frame capturado. Tentando fallback via poster/thumbnail...")
                        try:
                            poster_url = page.evaluate('() => document.querySelector("video")?.poster || ""')
                            if poster_url and poster_url.startswith("http"):
                                img_resp = requests.get(poster_url, timeout=10)
                                if img_resp.status_code == 200:
                                    midia_final = poster_url
                                    print(f"    ✅ Thumbnail recuperada com sucesso: {poster_url[:60]}...")
                                    
                                    # Auditoria do fallback
                                    post_id = href.strip("/").split("/")[-1]
                                    pasta_audit = os.path.join(PASTA_AUDITORIA_HOJE, alvo['username'], post_id)
                                    os.makedirs(pasta_audit, exist_ok=True)
                                    with open(os.path.join(pasta_audit, "thumbnail_fallback.jpg"), "wb") as f:
                                        f.write(img_resp.content)
                                else:
                                    print(f"    ❌ Falha ao baixar poster (status {img_resp.status_code})")
                            else:
                                print("    ❌ Nenhum poster/thumbnail disponível no elemento <video>.")
                        except Exception as e_poster:
                            print(f"    ❌ Erro no fallback de poster: {e_poster}")
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
                time.sleep(random.uniform(0.8, 2.2))
                page.keyboard.press("Escape")
                time.sleep(random.uniform(1.5, 3.0))
            
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
        # Parâmetros de camuflagem avançada para o Chromium
        chromium_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--start-maximized"
        ]
        chromium_ignore_args = ["--enable-automation"]
        modern_user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

        # Tenta abrir com perfil persistente, se falhar (perfil preso), abre um limpo
        try:
            print(f"🚀 Abrindo navegador com perfil persistente em: {os.path.basename(USER_DATA_DIR)}")
            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR, 
                headless=False,
                channel="chrome",
                args=chromium_args,
                ignore_default_args=chromium_ignore_args,
                viewport={"width": 1920, "height": 1080},
                user_agent=modern_user_agent,
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
                no_viewport=False # Importante para manter o estado da janela
            )
        except Exception as e:
            print("\n" + "!"*60)
            print(f"⚠️  ALERTA: PERFIL DE LOGIN BLOQUEADO OU INDISPONÍVEL!")
            print(f"   Erro: {e}")
            print(f"   AÇÃO: Verifique se há outra instância do Playwright aberta e feche-a.")
            print(f"   AVISO: Iniciando sessão TEMPORÁRIA. Logins não serão salvos nesta rodada.")
            print("!"*60 + "\n")
            
            # Fallback para navegador normal sem perfil
            browser_type = p.chromium.launch(
                headless=False,
                channel="chrome",
                args=chromium_args,
                ignore_default_args=chromium_ignore_args
            )
            browser = browser_type.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=modern_user_agent,
                locale="pt-BR",
                timezone_id="America/Sao_Paulo"
            )

        if len(browser.pages) > 0:
            browser.pages[0].close()

        page = browser.new_page()

        # 1. Primeiro: Atacar o site do Assaí (Ignora bloqueios de datacenter)
        processar_assai_site(page, historico, force=force)

        # 2. Mateus: Novo método unificado via Browser
        processar_mateus_site(page, historico, force=force)

        # 3. Segundo: Varredura nos perfis do Instagram
        processar_instagram(page, historico, force=force)
        
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
        print(f"  🧠 Rodando triagem [{janela_alvo}h] com: {venv_python}", flush=True)
        # Passa a janela como argumento para a triagem e o flag -u para unbuffered
        subprocess.run([venv_python, "-u", script_triagem, str(janela_alvo)], check=True)
        
        print("\n" + "="*60)
        print("🖼️ [AUTO-CURAÇÃO] Iniciando Curador de Imagens...")
        print("="*60)
        script_curacao = os.path.join(os.path.dirname(__file__), "completar_imagens.py")
        venv_functions_python = os.path.join(os.path.dirname(__file__), "..", "functions", "venv", "bin", "python3")
        subprocess.run([venv_functions_python, script_curacao, "--autopilot"], check=True)
        
        print("\n" + "="*60)
        print("🔄 [AUTO-SINCRONIZAÇÃO] Sincronizando imagens com ofertas...")
        print("="*60)
        script_sincronizacao = os.path.join(os.path.dirname(__file__), "sincronizar_imagens_ofertas.py")
        subprocess.run([venv_functions_python, script_sincronizacao], check=True)
        
    except Exception as e:
        print(f"⚠️ Erro ao iniciar triagem ou fluxos automáticos de imagem: {e}")
    
    print("\n=========================================================")
    print("🏁 CRON LOCAL FINALIZADO COM SUCESSO!")
    print("=========================================================")
