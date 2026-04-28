import os
import base64
import requests
import json
from datetime import datetime

# Configurações de conexão
ENDPOINT_FIREBASE = "https://extrair-dados-imagem-kcglywisya-uc.a.run.app"
SENHA_SEGURA = "senha_segura_123"

# Caminhos
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "auditoria_visual")
PASTA_TRIAGEM = os.path.join(BASE_DIR, "TRIAGEM_DE_OFERTAS")

# Mapeamento de IDs (Sincronizado com cron_playwright.py)
MAPEAMENTO_IDS = {
    "supermercadoslider": "lider-am",
    "formosaoficial": "formosa-am",
    "mmguerreirao": "guerreirao-br",
    "assaiatacadistaoficial": "assai-am",
    "assai_site": "assai"
}

def converter_para_b64(caminho_imagem):
    with open(caminho_imagem, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def enviar_para_nuvem():
    # 1. Identifica a pasta de hoje
    hoje = datetime.now().strftime("%Y-%m-%d")
    # Tenta achar a pasta que começa com a data de hoje
    pasta_hoje = ""
    for pasta in os.listdir(PASTA_TRIAGEM):
        if pasta.startswith(hoje):
            pasta_hoje = os.path.join(PASTA_TRIAGEM, pasta)
            break
            
    if not pasta_hoje or not os.path.exists(pasta_hoje):
        print(f"⚠️ Nenhuma triagem encontrada para hoje ({hoje}).")
        return

    print("="*60)
    print(f"🚀 INICIANDO ENVIO PARA NUVEM: {hoje}")
    print("="*60)

    # 2. Varre as janelas (10h, 14h, manual)
    janelas = [j for j in os.listdir(pasta_hoje) if os.path.isdir(os.path.join(pasta_hoje, j))]
    
    for janela in janelas:
        janela_path = os.path.join(pasta_hoje, janela)
        print(f"\n📂 Analisando janela: {janela}")

        # 3. Varre as lojas na janela
        for loja in os.listdir(janela_path):
            loja_path = os.path.join(janela_path, loja)
            if not os.path.isdir(loja_path): continue
            
            supermercado_id = MAPEAMENTO_IDS.get(loja.lower(), loja)
            
            # 4. Varre os posts da loja
            for post_id in os.listdir(loja_path):
                post_path = os.path.join(loja_path, post_id)
                if not os.path.isdir(post_path): continue
                
                print(f"\n📦 Processando: {loja} (ID: {supermercado_id}) | Post: {post_id} [{janela}]")
                
                # Coleta todas as imagens do post
                frames_b64 = []
                arquivos = sorted([f for f in os.listdir(post_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                
                for arq in arquivos:
                    print(f"  📸 Convertendo: {arq}")
                    frames_b64.append(converter_para_b64(os.path.join(post_path, arq)))
                
                if frames_b64:
                    # 5. Envia para o Firebase
                    payload = {
                        "supermercado_id": supermercado_id,
                        "post_id": post_id,
                        "frames_b64": frames_b64,
                        "senha": SENHA_SEGURA
                    }
                    
                    print(f"  🛰️ Enviando {len(frames_b64)} imagens para a nuvem...")
                    try:
                        resp = requests.post(ENDPOINT_FIREBASE, json=payload, timeout=120)
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("status") == "ignorado_duplicado":
                                print(f"  💰 ECONOMIA: Este post já foi processado hoje. (IA ignorada)")
                            else:
                                resumo = data.get("resumo", {})
                                extraidos = resumo.get("extraidos", 0)
                                salvos = resumo.get("novos_salvos", 0)
                                print(f"  ✅ SUCESSO! IA extraiu {extraidos} ofertas. ({salvos} novas)")
                        else:
                            print(f"  ❌ ERRO no Firebase: {resp.status_code}")
                    except Exception as e:
                        print(f"  ❌ ERRO de conexão: {e}")
                else:
                    print("  ⚠️ Nenhuma imagem encontrada neste post.")


    print("\n" + "="*60)
    print("🏁 PROCESSO DE ENVIO FINALIZADO!")
    print("="*60)

if __name__ == "__main__":
    enviar_para_nuvem()
