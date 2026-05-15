import os
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

USER_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "playwright_profile"))

def fazer_login():
    print("=========================================================")
    print("🔑 INICIANDO MODO DE LOGIN MANUAL - INSTAGRAM")
    print("=========================================================")
    
    with sync_playwright() as p:
        try:
            print(f"🚀 Abrindo navegador com perfil persistente...")
            
            stealth_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized"
            ]
            stealth_ignore_default_args = ["--enable-automation"]
            # Atualizado para uma versão recente do Chrome do Mac (v124)
            modern_user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR, 
                headless=False,
                channel="chrome",
                args=stealth_args,
                ignore_default_args=stealth_ignore_default_args,
                viewport={"width": 1920, "height": 1080},
                user_agent=modern_user_agent,
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
                no_viewport=False
            )
            
            # Fecha a primeira aba que nasce sem stealth
            if len(browser.pages) > 0:
                primeira_aba = browser.pages[0]
                primeira_aba.close()

            # Cria uma aba limpa ANTES de navegar
            page = browser.new_page()
            
            page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
            
            print("\n" + "!"*60)
            print("👉 O navegador foi aberto. Faça o seu login manualmente.")
            print("👉 Após fazer o login e ver a página inicial (feed),")
            print("👉 VOLTE AQUI NO TERMINAL E PRESSIONE [ENTER] PARA SALVAR.")
            print("!"*60 + "\n")
            
            input() # Fica pausado esperando o usuário dar Enter
            
            browser.close()
            print("✅ Navegador fechado. Seu login foi salvo na pasta do perfil!")
            
        except Exception as e:
            print(f"❌ Erro ao abrir. Feche todos os outros navegadores Chromium abertos. Erro: {e}")

if __name__ == "__main__":
    fazer_login()
