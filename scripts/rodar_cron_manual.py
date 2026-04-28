import requests
import json
import time

ENDPOINTS_DIRETOS = {
    "Atacadão (GraphQL)": "https://buscar-encarte-atacadao-kcglywisya-uc.a.run.app",
    "Seja Econômico (VipCommerce)": "https://buscar-encarte-economico-kcglywisya-uc.a.run.app",
    "Guerreirão AM (HTML)": "https://buscar-encarte-guerreirao-kcglywisya-uc.a.run.app"
}

def rodar_scrapers_diretos():
    print("\n🚀 INICIANDO SCRAPERS DIRETOS (Custo R$ 0.00 / Zero Tokens)")
    print("-" * 60)
    for nome, url in ENDPOINTS_DIRETOS.items():
        print(f"⏳ Processando {nome}...")
        inicio = time.time()
        try:
            resp = requests.get(url, timeout=30)
            dados = resp.json()
            if dados.get("sucesso"):
                print(f"  ✅ SUCESSO: {dados.get('quantidade')} itens salvos no Firestore.")
            else:
                print(f"  ❌ ERRO: {dados.get('erro')}")
        except Exception as e:
            print(f"  ❌ FALHA DE CONEXÃO: {e}")
        print(f"  ⏱️  Tempo: {time.time() - inicio:.2f}s\n")

def rodar_scraper_mateus():
    print("\n🧠 INICIANDO SCRAPER DE INTELIGÊNCIA ARTIFICIAL (Gemini 3.1 Flash Lite)")
    print("-" * 60)
    print("⏳ Passo 1: Buscando catálogo de PDFs do Mateus...")
    inicio = time.time()
    try:
        resp_catalogo = requests.get("https://buscar-encarte-mateus-kcglywisya-uc.a.run.app", timeout=30)
        catalogo = resp_catalogo.json().get("catalogo", [])
        
        if not catalogo:
            print("  ❌ Nenhum encarte encontrado no momento.")
            return

        primeiro_pdf = catalogo[0]
        link_pdf = primeiro_pdf["download_link"]
        print(f"  ✅ Catálogo recebido! PDF selecionado: {primeiro_pdf.get('titulo')}")
        print(f"⏳ Passo 2: Enviando PDF para o Gemini ler e salvar no Firestore...")
        
        payload = {"url": link_pdf, "supermercado_id": "mateus-jaderlandia", "loja": "Mix Mateus (Jaderlândia)"}
        resp_gemini = requests.post("https://extrair-dados-encarte-kcglywisya-uc.a.run.app", json=payload, timeout=120)
        dados_gemini = resp_gemini.json()
        
        if dados_gemini.get("sucesso"):
            print(f"  ✅ SUCESSO IA: {dados_gemini.get('quantidade')} itens extraídos.")
            print(f"  💾 FIRESTORE: {dados_gemini.get('salvos_firestore')} itens persistidos.")
            tokens = dados_gemini.get("uso_tokens", {})
            print(f"  🪙  CONSUMO: {tokens.get('total')} tokens totais (Prompt: {tokens.get('prompt')} | Resposta: {tokens.get('resposta')})")
        else:
            print(f"  ❌ ERRO IA: {dados_gemini.get('erro')}")
            
    except Exception as e:
        print(f"  ❌ FALHA GERAL IA: {e}")
    print(f"  ⏱️  Tempo total (Mateus): {time.time() - inicio:.2f}s\n")

if __name__ == "__main__":
    print("=========================================================")
    print("🤖 SIMULADOR DE CRON - VEJA O PREÇO (PRODUÇÃO)")
    print("=========================================================")
    rodar_scrapers_diretos()
    rodar_scraper_mateus()
    
    print("---------------------------------------------------------")
    print("⚠️ NOTA SOBRE LÍDER, FORMOSA E GUERREIRÃO BR:")
    print("A extração dessas redes (Instagram) agora é executada")
    print("pelo nosso Navegador Fantasma local. Para rodar, use:")
    print("python scripts/cron_playwright.py")
    print("=========================================================")
