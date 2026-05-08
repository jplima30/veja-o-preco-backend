import os
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "playwright_profile"))

def fazer_login():
    print("=========================================================")
    print("🔑 INICIANDO MODO DE LOGIN MANUAL - INSTAGRAM")
    print("=========================================================")
    
    with sync_playwright() as p:
        try:
            print(f"🚀 Abrindo navegador com perfil persistente...")
            browser = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR, 
                headless=False,
                viewport={"width": 1920, "height": 1080},
                no_viewport=False
            )
            
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://www.instagram.com/", timeout=60000)
            
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
