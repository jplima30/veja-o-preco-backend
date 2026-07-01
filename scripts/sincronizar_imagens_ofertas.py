import sys
import os

# Adiciona as pastas corretas ao Path para importação do Firebase Admin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore

if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
db = firestore.client()

def sincronizar_imagens():
    print("=========================================================")
    print("🔄 INICIANDO SINCRONIZAÇÃO DE IMAGENS DO PRODUTO PARA AS OFERTAS")
    print("=========================================================\n")
    
    print("⏳ Carregando produtos...")
    produtos_ref = db.collection("produtos")
    produtos = {doc.id: doc.to_dict() for doc in produtos_ref.stream()}
    print(f"✅ {len(produtos)} produtos carregados.")
    
    print("⏳ Carregando ofertas...")
    ofertas_ref = db.collection("ofertas")
    ofertas = list(ofertas_ref.stream())
    print(f"✅ {len(ofertas)} ofertas carregadas.")
    
    total_atualizadas = 0
    
    for of_doc in ofertas:
        of_data = of_doc.to_dict()
        prod_id = of_data.get("produto_id")
        of_img = of_data.get("imagem_url", "")
        
        if prod_id in produtos:
            prod_data = produtos[prod_id]
            prod_img = prod_data.get("imagem_url", "")
            
            # Se o produto tem imagem curada no Firestore e a oferta não tem ou tem imagem antiga
            # que seja diferente da do produto, atualiza a oferta!
            if prod_img and of_img != prod_img:
                print(f"🔄 Sincronizando oferta: '{of_data.get('produto_nome')}'")
                print(f"   De: {of_img[:60]}...")
                print(f"   Para: {prod_img[:60]}...")
                
                of_doc.reference.update({
                    "imagem_url": prod_img
                })
                total_atualizadas += 1
                
    print("\n=========================================================")
    print("🏁 SINCRONIZAÇÃO CONCLUÍDA!")
    print(f"🔄 Total de ofertas sincronizadas: {total_atualizadas}")
    print("=========================================================\n")

if __name__ == "__main__":
    try:
        sincronizar_imagens()
    except KeyboardInterrupt:
        print("\n\n👋 Operação cancelada pelo usuário.")
        sys.exit(0)
