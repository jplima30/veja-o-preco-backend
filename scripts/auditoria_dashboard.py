import os
import requests
import json
from datetime import datetime

# Configurações de conexão
ENDPOINT_STATUS = "https://get-status-extracao-kcglywisya-uc.a.run.app"

# Caminhos locais
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "auditoria_visual")
PASTA_TRIAGEM = os.path.join(BASE_DIR, "TRIAGEM_DE_OFERTAS")

def formatar_tabela(titulo, colunas, linhas):
    # Calcula largura das colunas
    larguras = [len(c) for c in colunas]
    for linha in linhas:
        for i, val in enumerate(linha):
            larguras[i] = max(larguras[i], len(str(val)))
    
    # Header
    print(f"\n--- {titulo} ---")
    header = " | ".join(f"{col:{larg}}" for col, larg in zip(colunas, larguras))
    print(header)
    print("-" * len(header))
    
    # Linhas
    for linha in linhas:
        print(" | ".join(f"{str(val):{larg}}" for val, larg in zip(linha, larguras)))

def auditoria_dashboard():
    print("="*60)
    print("📊 DASHBOARD DE AUDITORIA: LOCAL vs NUVEM")
    print("="*60)

    # 1. Busca status da nuvem
    print("🛰️ Consultando Firebase Firestore...")
    try:
        resp = requests.get(ENDPOINT_STATUS, timeout=30)
        if resp.status_code != 200:
            print(f"❌ Erro ao consultar nuvem: {resp.status_code}")
            return
        nuvem_data = resp.json().get("processados", {})
    except Exception as e:
        print(f"❌ Falha de conexão com a nuvem: {e}")
        return

    # 2. Varre pastas locais
    # Identifica a pasta de hoje
    hoje_str = datetime.now().strftime("%Y-%m-%d")
    pasta_hoje = ""
    for p in os.listdir(PASTA_TRIAGEM) if os.path.exists(PASTA_TRIAGEM) else []:
        if p.startswith(hoje_str):
            pasta_hoje = os.path.join(PASTA_TRIAGEM, p)
            break
    
    if not pasta_hoje:
        print(f"⚠️ Nenhuma pasta de triagem encontrada para hoje ({hoje_str}).")
        return

    print(f"📁 Analisando pastas locais em: {os.path.basename(pasta_hoje)}")
    
    linhas_tabela = []
    
    # 3. Compara Lojas e Posts
    for janela in sorted(os.listdir(pasta_hoje)):
        janela_path = os.path.join(pasta_hoje, janela)
        if not os.path.isdir(janela_path): continue
        
        # Pode ser que a janela seja direto a loja ou a pasta 10h/14h
        lojas = []
        if janela in ["10h", "14h", "manual"]:
            lojas = [os.path.join(janela_path, l) for l in os.listdir(janela_path) if os.path.isdir(os.path.join(janela_path, l))]
            contexto = janela
        else:
            lojas = [janela_path]
            contexto = "Geral"

        for loja_path in lojas:
            loja_nome = os.path.basename(loja_path)
            # Tenta mapear o ID igual no enviar_triagem
            mapeamento = {
                "supermercadoslider": "lider-am",
                "formosaoficial": "formosa-am",
                "mmguerreirao": "guerreirao-br",
                "assaiatacadistaoficial": "assai-am"
            }
            loja_id = mapeamento.get(loja_nome.lower(), loja_nome)
            
            posts_locais = [p for p in os.listdir(loja_path) if os.path.isdir(os.path.join(loja_path, p))]
            posts_nuvem = nuvem_data.get(loja_id, [])

            for pid in posts_locais:
                status = "✅ SINCRONIZADO" if pid in posts_nuvem else "⚠️ PENDENTE (Local)"
                linhas_tabela.append([contexto, loja_id, pid, status])

    # 4. Exibe Resultados
    if not linhas_tabela:
        print("🤷 Nenhuma triagem local encontrada para comparar.")
    else:
        formatar_tabela("RESUMO DE SINCRONIZAÇÃO", ["JANELA", "LOJA", "POST_ID", "STATUS"], linhas_tabela)

    print("\n" + "="*60)
    print("🏁 AUDITORIA FINALIZADA")
    print("="*60)

if __name__ == "__main__":
    auditoria_dashboard()
