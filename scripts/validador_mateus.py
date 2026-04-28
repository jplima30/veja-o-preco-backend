import requests
import json
import sys

def validar_mateus():
    """
    Testa o fluxo completo do Mateus:
    1. Busca o link do PDF.
    2. Envia para a extração via Gemini.
    """
    base_url = "http://127.0.0.1:5001/veja-o-preco/us-central1"
    
    print("🔍 [1/2] Buscando link do encarte mais recente...")
    try:
        resp_busca = requests.get(f"{base_url}/buscar_encarte_mateus")
        resp_busca.raise_for_status()
        dados_busca = resp_busca.json()
        
        pdf_url = dados_busca.get("download_link")
        if not pdf_url:
            print("❌ Erro: Link do PDF não encontrado.")
            return

        print(f"✅ PDF encontrado: {pdf_url}")
        print("\n🧠 [2/2] Enviando para o Cérebro Gemini (Isso pode levar 20s)...")
        
        resp_extrair = requests.get(f"{base_url}/extrair_dados_encarte", params={"url": pdf_url}, timeout=60)
        resp_extrair.raise_for_status()
        dados_finais = resp_extrair.json()
        
        if dados_finais.get("sucesso"):
            print(f"🎉 SUCESSO! Extraídos {dados_finais.get('quantidade')} itens.")
            print("\n--- Amostra dos 3 primeiros itens ---")
            for item in dados_finais.get("itens", [])[:3]:
                print(f"🛒 {item['produto']} - R$ {item['preco']}")
        else:
            print(f"❌ Falha na extração: {dados_finais.get('erro')}")

    except Exception as e:
        print(f"💥 Erro crítico: {e}")

if __name__ == "__main__":
    validar_mateus()
