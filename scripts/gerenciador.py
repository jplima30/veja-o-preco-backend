import os
import sys
import subprocess
import time

# Resolve o diretório raiz do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Atalhos para os executáveis Python nos ambientes virtuais
VENV_TRIAGEM = "venv_triagem/bin/python3"
VENV_FUNCTIONS = "functions/venv/bin/python3"

def executar_script(python_rel_path: str, script_name: str, args: list = None):
    py_exec = os.path.join(BASE_DIR, python_rel_path)
    scr_path = os.path.join(BASE_DIR, "scripts", script_name)
    
    if not os.path.exists(py_exec):
        print(f"❌ Erro: Ambiente virtual não encontrado em: {py_exec}")
        input("\nPressione Enter para continuar...")
        return
        
    if not os.path.exists(scr_path):
        print(f"❌ Erro: Script não encontrado em: {scr_path}")
        input("\nPressione Enter para continuar...")
        return

    cmd = [py_exec, scr_path]
    if args:
        cmd.extend(args)
        
    print(f"\n🚀 Executando: {' '.join(cmd)}")
    print("---------------------------------------------------------")
    try:
        # Usa subprocess.run para passar o controle do terminal (stdin/stdout) de forma síncrona
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Erro durante a execução: {e}")
    except KeyboardInterrupt:
        print("\n👋 Execução interrompida pelo usuário.")
    print("---------------------------------------------------------")
    input("\nPressione Enter para voltar...")

def ver_log(log_name: str):
    log_path = os.path.join(BASE_DIR, "scripts", log_name)
    if not os.path.exists(log_path):
        print(f"\n⚠️ Arquivo de log '{log_name}' não encontrado.")
    else:
        print(f"\n📄 Exibindo as últimas 50 linhas de {log_name}:\n")
        print("=========================================================")
        try:
            with open(log_path, "r", errors="ignore") as f:
                linhas = f.readlines()
                for linha in linhas[-50:]:
                    print(linha, end="")
        except Exception as e:
            print(f"Erro ao ler log: {e}")
        print("=========================================================")
    input("\nPressione Enter para voltar...")

# --- SUBMENUS ---

def menu_coleta():
    while True:
        os.system("clear")
        print("=========================================================")
        print("🤖 CATEGORIA 1: COLETA, SCRAPING & AUTENTICAÇÃO")
        print("=========================================================")
        print("  [1] 🕷️  Iniciar Robô de Captura Geral (cron_playwright.py)")
        print("      👉 Roda a varredura programada do Instagram/Redes Sociais.")
        print("  [2] 🔑 Renovar Login do Instagram (logar_instagram.py)")
        print("      👉 Abre o navegador para autenticar e salvar perfil.")
        print("  [3] 📑 Exibir Logs do Cron Principal (cron_playwright.log)")
        print("  [4] 📑 Exibir Logs de Captura de Hoje (cron_hoje.log)")
        print("  [0] 🔙 Voltar ao Menu Principal")
        print("=========================================================")
        opcao = input("👉 Escolha uma opção [0-4]: ").strip()
        
        if opcao == "0":
            break
        elif opcao == "1":
            executar_script(VENV_TRIAGEM, "cron_playwright.py")
        elif opcao == "2":
            executar_script(VENV_TRIAGEM, "logar_instagram.py")
        elif opcao == "3":
            ver_log("cron_playwright.log")
        elif opcao == "4":
            ver_log("cron_hoje.log")

def menu_triagem():
    while True:
        os.system("clear")
        print("=========================================================")
        print("🔍 CATEGORIA 2: TRIAGEM LOCAL & I.A. VISION")
        print("=========================================================")
        print("  [1] ⚙️  Executar Triagem por OCR Local (triagem_automatizada.py)")
        print("      👉 Filtra as imagens brutas antes do envio para a nuvem.")
        print("  [2] 🎨 Depurar OCR Local Visualmente (triagem_local.py)")
        print("      👉 Exibe retângulos de detecção de preços nas imagens.")
        print("  [3] ☁️  Forçar Envio para Cloud (enviar_triagem.py)")
        print("      👉 Envia imagens triadas para o endpoint de processamento.")
        print("  [4] 🧪 Testar API do Gemini Vision (testar_visao.py)")
        print("      👉 Envia imagem de teste direta para checagem da IA.")
        print("  [0] 🔙 Voltar ao Menu Principal")
        print("=========================================================")
        opcao = input("👉 Escolha uma opção [0-4]: ").strip()
        
        if opcao == "0":
            break
        elif opcao == "1":
            executar_script(VENV_TRIAGEM, "triagem_automatizada.py")
        elif opcao == "2":
            executar_script(VENV_TRIAGEM, "triagem_local.py")
        elif opcao == "3":
            executar_script(VENV_TRIAGEM, "enviar_triagem.py")
        elif opcao == "4":
            executar_script(VENV_FUNCTIONS, "testar_visao.py")

def menu_validadores():
    while True:
        os.system("clear")
        print("=========================================================")
        print("🛒 CATEGORIA 3: CONECTORES E VALIDADORES DE LOJAS")
        print("=========================================================")
        print("  [1] 🐂 Rodar Validador Mix Mateus (validador_mateus.py)")
        print("  [2] 🛒 Rodar Validador Atacadão (validador_atacadao.py)")
        print("  [3] 💰 Rodar Validador Seja Econômico (validador_economico.py)")
        print("  [4] 🏪 Rodar Validador Guerreirão (validador_guerreirao.py)")
        print("  [0] 🔙 Voltar ao Menu Principal")
        print("=========================================================")
        opcao = input("👉 Escolha uma opção [0-4]: ").strip()
        
        if opcao == "0":
            break
        elif opcao == "1":
            executar_script(VENV_FUNCTIONS, "validador_mateus.py")
        elif opcao == "2":
            executar_script(VENV_FUNCTIONS, "validador_atacadao.py")
        elif opcao == "3":
            executar_script(VENV_FUNCTIONS, "validador_economico.py")
        elif opcao == "4":
            executar_script(VENV_FUNCTIONS, "validador_guerreirao.py")

def menu_curadoria():
    while True:
        os.system("clear")
        print("=========================================================")
        print("🧹 CATEGORIA 4: HIGIENIZAÇÃO & CURADORIA DE CATÁLOGO")
        print("=========================================================")
        print("  [1] 🖼️  Abrir Central de Imagens Interativa (central_imagens.py)")
        print("  [2] 🔄 Mesclagem Automática de Produtos (Lote completo)")
        print("  [3] ✂️  Mesclagem Manual de Produtos (União Cirúrgica)")
        print("  [4] 🧠 Assistente de Duplicatas Inteligente (Fuzzy Matching)")
        print("  [5] 🔞 Limpar Bebidas Alcoólicas / Proibidas (limpar_bebidas.py)")
        print("  [6] 🧹 Assistente de Auditoria de Categorias (auditar_categorias.py)")
        print("  [0] 🔙 Voltar ao Menu Principal")
        print("=========================================================")
        opcao = input("👉 Escolha uma opção [0-6]: ").strip()
        
        if opcao == "0":
            break
        elif opcao == "1":
            executar_script(VENV_FUNCTIONS, "central_imagens.py")
        elif opcao == "2":
            executar_script(VENV_FUNCTIONS, "mesclar_produtos.py")
        elif opcao == "3":
            id_de = input("👉 Digite o ID de origem (duplicado/com erro): ").strip()
            id_para = input("👉 Digite o ID de destino (correto): ").strip()
            if id_de and id_para:
                executar_script(VENV_FUNCTIONS, "mesclar_produtos.py", ["--de", id_de, "--para", id_para])
            else:
                print("⚠️ Erro: Ambos os IDs são necessários para a mesclagem.")
                input("\nPressione Enter para continuar...")
        elif opcao == "4":
            executar_script(VENV_FUNCTIONS, "identificar_duplicatas.py")
        elif opcao == "5":
            executar_script(VENV_FUNCTIONS, "limpar_bebidas.py")
        elif opcao == "6":
            executar_script(VENV_FUNCTIONS, "auditar_categorias.py")

def menu_relatorios():
    while True:
        os.system("clear")
        print("=========================================================")
        print("📊 CATEGORIA 5: MONITORAMENTO, LOGS & DIAGNÓSTICO")
        print("=========================================================")
        print("  [1] 🏥 Dashboard de Saúde e Cobertura (auditoria_dashboard.py)")
        print("  [2] 📝 Exibir Resumo das Ofertas de Hoje (resumo_hoje.py)")
        print("  [3] 🗄️  Listar Ofertas Ativas no App/Firestore (ver_ofertas_banco.py)")
        print("  [0] 🔙 Voltar ao Menu Principal")
        print("=========================================================")
        opcao = input("👉 Escolha uma opção [0-3]: ").strip()
        
        if opcao == "0":
            break
        elif opcao == "1":
            executar_script(VENV_TRIAGEM, "auditoria_dashboard.py")
        elif opcao == "2":
            executar_script(VENV_FUNCTIONS, "resumo_hoje.py")
        elif opcao == "3":
            executar_script(VENV_FUNCTIONS, "ver_ofertas_banco.py")

def menu_testes():
    while True:
        os.system("clear")
        print("=========================================================")
        print("🧪 CATEGORIA 6: TESTES & INICIALIZAÇÃO DE AMBIENTE")
        print("=========================================================")
        print("  [1] 🌱 Popular Firestore Local (seed_firestore.py)")
        print("  [2] 🧬 Rodar Teste de Integração Completo (testar_integracao.py)")
        print("  [3] 🌐 Testar Playwright Chromium Local (test_playwright.py)")
        print("  [4] 🍎 Testar Playwright WebKit Local (test_playwright_webkit.py)")
        print("  [0] 🔙 Voltar ao Menu Principal")
        print("=========================================================")
        opcao = input("👉 Escolha uma opção [0-4]: ").strip()
        
        if opcao == "0":
            break
        elif opcao == "1":
            executar_script(VENV_FUNCTIONS, "seed_firestore.py")
        elif opcao == "2":
            executar_script(VENV_FUNCTIONS, "testar_integracao.py")
        elif opcao == "3":
            executar_script(VENV_TRIAGEM, "test_playwright.py")
        elif opcao == "4":
            executar_script(VENV_TRIAGEM, "test_playwright_webkit.py")

def menu_principal():
    while True:
        os.system("clear")
        print("=========================================================")
        print("⚡ PANEL DE CONTROLE BACKEND — VEJA O PREÇO")
        print("=========================================================")
        print("  [1] 🤖 COLETA & CRAWLERS (Playwright, Instagram, Logs)")
        print("  [2] 🔍 TRIAGEM & OCR (EasyOCR Local, Enviar para Cloud)")
        print("  [3] 🛒 CONECTORES DE LOJAS (Validadores das Redes)")
        print("  [4] 🧹 HIGIENIZAÇÃO & CURADORIA (Central Imagens, Mesclador)")
        print("  [5] 📊 MONITORAMENTO & RELATÓRIOS (Saúde, Resumos, Banco)")
        print("  [6] 🧪 TESTES & AMBIENTE (Seed, Integração, Scrapers)")
        print("  [0] 🚪 Sair")
        print("=========================================================")
        opcao = input("👉 Digite a categoria desejada [0-6]: ").strip()
        
        if opcao == "0":
            print("\n👋 Saindo do Painel de Controle. Até logo!")
            break
        elif opcao == "1":
            menu_coleta()
        elif opcao == "2":
            menu_triagem()
        elif opcao == "3":
            menu_validadores()
        elif opcao == "4":
            menu_curadoria()
        elif opcao == "5":
            menu_relatorios()
        elif opcao == "6":
            menu_testes()

if __name__ == "__main__":
    try:
        menu_principal()
    except KeyboardInterrupt:
        print("\n\n👋 Painel encerrado pelo usuário.")
        sys.exit(0)
