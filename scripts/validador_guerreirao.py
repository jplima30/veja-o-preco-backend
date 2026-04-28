import requests
from bs4 import BeautifulSoup
import json

def validar_guerreirao():
    url = "https://portal.qrofertas.com/meio-a-meio-o-guerreiro/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    print(f"--- Verificando Saúde do Scraper: Guerreirão ---")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            print("[OK] Conexão estabelecida.")
        else:
            print(f"[ERRO] Status Code: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.select(".boxProdutoEst")
        
        if len(cards) > 0:
            print(f"[OK] {len(cards)} produtos detectados na vitrine.")
            
            # Valida o primeiro item
            primeiro = cards[0]
            nome = primeiro.select_one('[itemprop="name"]').get_text(strip=True) if primeiro.select_one('[itemprop="name"]') else "N/A"
            preco = primeiro.select_one('[itemprop="price"]').get_text(strip=True) if primeiro.select_one('[itemprop="price"]') else "N/A"
            
            print(f"[INFO] Amostra: {nome} - R$ {preco}")
            print("\n--- Scraper Saudável ---")
        else:
            print("[ALERTA] Nenhum produto encontrado. O site pode ter mudado a estrutura!")

    except Exception as e:
        print(f"[ERRO CRÍTICO] Falha na execução: {e}")

if __name__ == "__main__":
    validar_guerreirao()

# comando p/ executar esse script 
# functions/venv/bin/python3 scripts/validador_guerreirao.py