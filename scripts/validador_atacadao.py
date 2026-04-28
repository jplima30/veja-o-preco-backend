import requests
import json
import base64

def validar_atacadao():
    url = "https://www.atacadao.com.br/api/graphql"
    seller_id = "atacadaobr153" # Loja Belém
    
    print(f"--- Verificando Saúde do Scraper: Atacadão ({seller_id}) ---")
    
    try:
        # Gerando a regionalização que o Atacadão exige
        region_id = base64.b64encode(f"SW#{seller_id}".encode()).decode()
        
        channel = {
            "salesChannel": "1",
            "seller": seller_id,
            "regionId": region_id
        }
        
        variables = {
            "first": 5,
            "after": "0",
            "sort": "score_desc",
            "term": "",
            "selectedFacets": [
                {"key": "region-id", "value": region_id},
                {"key": "channel", "value": json.dumps(channel)},
                {"key": "locale", "value": "pt-BR"},
                {"key": "productClusterIds", "value": "312"}
            ]
        }
        
        params = {
            "operationName": "ProductsQuery",
            "variables": json.dumps(variables)
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*"
        }

        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            print("[OK] Conexão com GraphQL estabelecida.")
            dados = response.json()
            produtos = dados.get("data", {}).get("search", {}).get("products", {}).get("edges", [])
            
            if len(produtos) > 0:
                print(f"[OK] {len(produtos)} produtos detectados na vitrine.")
                p = produtos[0].get("node", {})
                nome = p.get("name")
                preco = p.get("offers", {}).get("lowPrice", "N/A")
                print(f"[INFO] Amostra: {nome} - R$ {preco}")
                print("\n--- Scraper Saudável ---")
            else:
                print("[ALERTA] Nenhum produto encontrado. Verifique se o ClusterID 312 ainda é válido.")
        else:
            print(f"[ERRO] Status Code: {response.status_code}")
            print(f"[DEBUG] Resposta: {response.text[:200]}")

    except Exception as e:
        print(f"[ERRO CRÍTICO] Falha na execução: {e}")

if __name__ == "__main__":
    validar_atacadao()

# comando p/ executar esse script 
# functions/venv/bin/python3 scripts/validador_atacadao.py
