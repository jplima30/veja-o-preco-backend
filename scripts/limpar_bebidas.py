import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import credentials, firestore

# Inicializa o app com as credenciais locais e o ID do projeto explícito
if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
    
db = firestore.client()

palavras_proibidas = [
    "cerveja", "whisky", "whiskey", "vodka", "vodca", "gin", "vinho", 
    "chopp", "cachaça", "licor", "tequila", "rum", "ice", "skol", 
    "brahma", "heineken", "budweiser", "spaten", "amstel", "corona",
    "stella", "antarctica", "itaipava", "schin", "kaiser", "bavaria",
    "campari", "absolut", "smirnoff", "chandon", "espumante", "champagne"
]

def limpar_banco():
    print("=========================================================")
    print("🧹 LIMPANDO BEBIDAS ALCOÓLICAS DO FIRESTORE")
    print("=========================================================")
    
    apagados_produtos = 0
    apagados_ofertas = 0

    try:
        import re
        
        # 1. Limpar /produtos
        print("\nBuscando na coleção 'produtos'...")
        produtos_ref = db.collection("produtos").stream()
        for doc in produtos_ref:
            dados = doc.to_dict()
            nome = dados.get("nome", "").lower()
            if any(re.search(rf'\b{p}\b', nome) for p in palavras_proibidas):
                print(f"  🗑️ Apagando PRODUTO: {nome}")
                doc.reference.delete()
                apagados_produtos += 1

        # 2. Limpar /ofertas
        print("\nBuscando na coleção 'ofertas'...")
        ofertas_ref = db.collection("ofertas").stream()
        for doc in ofertas_ref:
            dados = doc.to_dict()
            nome = dados.get("produto_nome", "").lower()
            if any(re.search(rf'\b{p}\b', nome) for p in palavras_proibidas):
                print(f"  🗑️ Apagando OFERTA: {nome}")
                doc.reference.delete()
                apagados_ofertas += 1

        print("\n✅ LIMPEZA CONCLUÍDA!")
        print(f"   Total de Produtos apagados: {apagados_produtos}")
        print(f"   Total de Ofertas apagadas: {apagados_ofertas}")
        print("=========================================================")
    except Exception as e:
        print(f"Erro ao limpar banco: {e}")

if __name__ == "__main__":
    limpar_banco()
