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
            elif origem == "auto_crop_aceito":
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
        print(f"     - Recorte aceito (IA):         {stats['auto_crop_aceito']} ({p_aceito:.1f}%)")
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
                
    print("\n=========================================================")
    print("🏁 SINCRONIZAÇÃO CONCLUÍDA!")
    print(f"🔄 Total de ofertas sincronizadas: {total_atualizadas}")
    print("=========================================================\n")

def executar_diagnostico(db):
    print("=========================================================")
    print("🔎 BUSCANDO OFERTAS VIGENTES SEM IMAGEM NO FIRESTORE")
    print("=========================================================\n")
    
    hoje = datetime.now()
    ofertas_ref = db.collection("ofertas").where("expira_em", ">=", hoje)
    docs = ofertas_ref.stream()
    
    sem_imagem = []
    total_vigentes = 0
    
    for doc in docs:
        total_vigentes += 1
        d = doc.to_dict()
        img = d.get("imagem_url", "").strip()
        
        if not img:
            sem_imagem.append((doc.id, d))
            
    print(f"📊 Total de ofertas vigentes encontradas: {total_vigentes}")
    print(f"❌ Total de ofertas vigentes SEM IMAGEM: {len(sem_imagem)}")
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
    else:
        print("🎉 Excelente! Todas as ofertas vigentes possuem imagem!")
    print()

def executar_curadoria(db, bucket, opcao_modo: str):
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
        
        incluir = False
        if opcao_modo == "1":
            # Apenas sem imagem
            incluir = (not url)
        elif opcao_modo == "2":
            # Apenas recortes IA
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
            
        if incluir:
            produtos_pendentes.append((doc.id, d))
            
    if not produtos_pendentes:
        print("🎉 Nenhum produto pendente de curação no modo selecionado!")
        return
        
    print(f"📂 Encontrados {len(produtos_pendentes)} produtos correspondentes.")
    print("---------------------------------------------------------")
    
    total_atualizados = 0
    is_autopilot = (opcao_modo == "5")
    
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
            
            # Passo 1: Busca automática de imagens no DuckDuckGo
            print("   🔍 Buscando no DuckDuckGo Images...")
            urls_ddg = buscar_duckduckgo_images(nome)
            
            if urls_ddg:
                print(f"   🌐 Encontradas {len(urls_ddg)} imagens no DuckDuckGo.")
                sucesso_download = False
                
                for idx, url_temp in enumerate(urls_ddg):
                    print(f"     [Tentativa {idx+1}/{len(urls_ddg)}] Testando: {url_temp}")
                    
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
                    print("   ❌ Nenhuma das imagens do DuckDuckGo pós-download funcionou.")
            else:
                print("   ❌ Não encontrado no DuckDuckGo.")
                
            if pular_produto:
                break
                
            # Passo 2: Entrada manual caso nenhuma automática tenha sido bem-sucedida
            if not url_selecionada:
                if is_autopilot:
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
        
        print("SELECIONE A AÇÃO DESEJADA:")
        print("  [1] CURADORIA INTERATIVA (Apenas produtos que não possuem NENHUMA imagem cadastrada)")
        print("      👉 O script buscará no DuckDuckGo e perguntará antes de salvar cada foto de estúdio.")
        print("  [2] CURADORIA INTERATIVA (Apenas produtos com recortes temporários da IA [auto_crop])")
        print("      👉 Útil para substituir fotos de baixa qualidade ou cortadas por fotos de estúdio limpas.")
        print("  [3] CURADORIA INTERATIVA (Apenas produtos com recortes da IA marcados como aceitos [auto_crop_aceito])")
        print("      👉 Permite revisar e substituir imagens de recortes que foram aceitas anteriormente.")
        print("  [4] CURADORIA INTERATIVA (Tudo: sem imagem + recortes temporários + recortes aceitos)")
        print("      👉 Varredura manual interativa completa de todo o catálogo.")
        print("  [5] PILOTO AUTOMÁTICO (Busca DuckDuckGo em lote - 100% silencioso e automatizado)")
        print("      👉 Baixa, otimiza e salva fotos de forma silenciosa para itens sem imagem ou com auto_crop.")
        print("  [6] SINCRONIZAR OFERTAS (Copiar imagens do catálogo para as ofertas vigentes)")
        print("      👉 Copia as fotos de /produtos para /ofertas ativas no app iOS.")
        print("  [7] DIAGNÓSTICO DO BANCO (Listar estatísticas gerais e ofertas vigentes sem foto)")
        print("      👉 Mostra o status atual de cobertura do banco de dados e detalha as pendências.")
        print("  [0] SAIR")
        
        opcao = input("\n👉 Digite a opção desejada [0-7]: ").strip()
        
        if opcao == "0":
            print("\n👋 Saindo da Central de Imagens. Até logo!")
            break
        elif opcao in ("1", "2", "3", "4", "5"):
            executar_curadoria(db, bucket, opcao)
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
