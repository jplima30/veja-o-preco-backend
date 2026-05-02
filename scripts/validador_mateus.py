import requests
import json
import sys

def validar_mateus():
    """
    Testa o fluxo completo do Mateus:
    1. Busca a lista de encartes.
    2. Permite selecionar qual encarte processar.
    3. Envia para a extração via Gemini.
    """
    # Usar 127.0.0.1 em vez de localhost evita problemas de resolução/sandbox no macOS
    base_url = "http://127.0.0.1:5001/veja-o-preco/us-central1"
    
    # Desativa trust_env para evitar crash de rede no macOS
    session = requests.Session()
    session.trust_env = False
    
    print("🔍 [1/2] Buscando catálogo de encartes...")
    try:
        resp_busca = session.get(f"{base_url}/buscar_encarte_mateus")
        resp_busca.raise_for_status()
        dados_busca = resp_busca.json()
        
        catalogo = dados_busca.get("catalogo", [])
        if not catalogo:
            print("❌ Erro: Catálogo de encartes vazio.")
            return
            
        print(f"\n📂 Encartes encontrados ({len(catalogo)}):")
        for i, item in enumerate(catalogo):
            print(f"   [{i}] {item.get('titulo')} (Início: {item.get('data_inicio_tela')})")
        
        # Lógica de seleção: por padrão processa TODOS os únicos. 
        # Se passar um número, processa apenas aquele índice.
        
        vistos = set()
        indices_unicos = []
        for i, item in enumerate(catalogo):
            url = item.get("download_link")
            if url not in vistos:
                vistos.add(url)
                indices_unicos.append(i)
        
        indices_para_processar = indices_unicos
        
        if len(sys.argv) > 1:
            arg = sys.argv[1].lower()
            try:
                idx = int(arg)
                if 0 <= idx < len(catalogo):
                    indices_para_processar = [idx]
                    print(f"\n🎯 MODO INDIVIDUAL: Processando apenas o índice [{idx}].")
                else:
                    print(f"⚠️ Índice {idx} fora do intervalo. Usando modo 'all'.")
            except ValueError:
                if arg != "all":
                    print("⚠️ Argumento não reconhecido. Use um número para modo individual ou 'all' para todos.")
                else:
                    print("\n🚀 MODO TOTAL: Processando todos os encartes únicos.")
        else:
            print(f"\n🚀 MODO PADRÃO: Processando {len(indices_para_processar)} encartes únicos encontrados.")

        for idx in indices_para_processar:
            escolhido = catalogo[idx]
            pdf_url = escolhido.get("download_link")
            titulo = escolhido.get("titulo")
            
            print(f"\n--- [{idx+1}/{len(indices_para_processar)}] Processando: {titulo} ---")
            print(f"🔗 Link: {pdf_url}")
            
            print("🧠 Enviando para o Cérebro Gemini (pode levar 20s)...")
            
            try:
                resp_extrair = session.get(f"{base_url}/extrair_dados_encarte", params={"url": pdf_url}, timeout=300)
                resp_extrair.raise_for_status()
                dados_finais = resp_extrair.json()
                
                if dados_finais.get("sucesso"):
                    itens = dados_finais.get("itens", [])
                    print(f"🎉 SUCESSO! Extraídos {len(itens)} itens.")
                    
                    if itens:
                        print(f"🛒 Amostra: {', '.join([i['produto'] for i in itens[:3]])}...")
                    else:
                        print("ℹ️ A IA não encontrou produtos de supermercado válidos neste PDF.")
                else:
                    print(f"❌ Falha na extração: {dados_finais.get('erro')}")
            except Exception as e_proc:
                print(f"💥 Erro ao processar este encarte: {e_proc}")

    except Exception as e:
        print(f"💥 Erro crítico: {e}")

if __name__ == "__main__":
    validar_mateus()
