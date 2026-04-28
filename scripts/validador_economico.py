import requests
import json

def validar_economico():
    org_id = "315"
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{org_id}/filial/1/centro_distribuicao/1/loja/produtos/em-oferta"
    
    print(f"--- Verificando Saúde do Scraper: Seja Econômico (Ofertas Oficiais) ---")
    
    # Cabeçalhos de Identificação (Extraídos do site real)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "DomainKey": "grupoeconomico.com.br",
        "OrganizationId": org_id,
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NzY3MTc0ODMsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMzE1In0.VsuwHCwfq-CF9yUzkGv6ekV--zAMmtWtPm-H6dbazQvC6GYp5spDx32GlWJEogReqDKU_TWscSNRW070elQDPA"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            print("[OK] Conexão com API VipCommerce estabelecida.")
            dados = response.json()
            produtos = dados.get("data", [])
            
            if len(produtos) > 0:
                print(f"[OK] {len(produtos)} produtos retornados na vitrine de ofertas.")
                p = produtos[0]
                nome = p.get("descricao", "N/A")
                preco = p.get("preco_venda", "N/A")
                print(f"[INFO] Amostra: {nome} - R$ {preco}")
                print("\n--- Scraper Saudável ---")
            else:
                print("[ALERTA] API respondeu mas a lista de produtos veio vazia. Verifique o Bearer Token.")
        elif response.status_code == 403:
            print("[ERRO] 403 Forbidden. O Bearer Token expirou e precisa ser renovado.")
        else:
            print(f"[ERRO] Status Code: {response.status_code}")

    except Exception as e:
        print(f"[ERRO CRÍTICO] Falha na execução: {e}")

if __name__ == "__main__":
    validar_economico()
