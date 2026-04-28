import requests
import json
import sys

def testar_extracao_visao(url_imagem):
    """
    Script utilitário para testar a função extrair_dados_imagem no emulador local.
    """
    url_local = "http://127.0.0.1:5001/veja-o-preco/us-central1/extrair_dados_imagem"
    
    payload = {
        "url": url_imagem
    }
    
    print(f"🚀 Iniciando teste de Visão Computacional...")
    print(f"📸 Imagem: {url_imagem}")
    print(f"🔗 Chamando: {url_local}\n")
    
    try:
        response = requests.post(url_local, json=payload)
        response.raise_for_status()
        
        resultado = response.json()
        print("✅ Resultado da Extração:")
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        
        if resultado.get("sucesso"):
            print(f"\n🎯 Sucesso! Encontrados {resultado.get('quantidade')} itens.")
            print(f"💰 Tokens usados: {resultado.get('uso_tokens', {}).get('total', 'N/A')}")
            
    except Exception as e:
        print(f"❌ Erro ao chamar o emulador: {e}")
        print("Certifique-se de que o emulador do Firebase está rodando!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 scripts/testar_visao.py 'URL_DA_IMAGEM'")
    else:
        testar_extracao_visao(sys.argv[1])
