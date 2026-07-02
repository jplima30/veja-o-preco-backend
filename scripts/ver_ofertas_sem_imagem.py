import sys
import os
from datetime import datetime

# Adiciona a pasta raiz e a pasta functions no path para conseguir importar o Firebase Admin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore

if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
db = firestore.client()

def listar_ofertas_sem_imagem():
    print("=========================================================")
    print("🔎 BUSCANDO OFERTAS VIGENTES SEM IMAGEM NO FIRESTORE")
    print("=========================================================\n")
    
    # Filtra apenas ofertas que não expiraram
    hoje = datetime.now()
    ofertas_ref = db.collection("ofertas").where("expira_em", ">=", hoje)
    docs = ofertas_ref.stream()
    
    sem_imagem = []
    total_vigentes = 0
    
    for doc in docs:
        total_vigentes += 1
        d = doc.to_dict()
        img = d.get("imagem_url", "").strip()
        
        # Considera sem imagem se o campo estiver vazio ou nulo
        if not img:
            sem_imagem.append((doc.id, d))
            
    print(f"📊 Total de ofertas vigentes encontradas: {total_vigentes}")
    print(f"❌ Total de ofertas vigentes SEM IMAGEM: {len(sem_imagem)}")
    print("---------------------------------------------------------\n")
    
    if sem_imagem:
        print("📋 Amostra das primeiras 30 ofertas sem imagem:")
        for i, (doc_id, d) in enumerate(sem_imagem[:30]):
            loja = d.get("loja", "Desconhecida")
            nome = d.get("produto_nome", "Sem nome")
            preco = d.get("preco", 0)
            validade = d.get("validade", "Desconhecida")
            print(f"  [{i+1}] 🛒 {nome} - R$ {preco:.2f} ({loja}) | Validade: {validade}")
        
        if len(sem_imagem) > 30:
            print(f"\n... e mais {len(sem_imagem) - 30} ofertas sem imagem.")
    else:
        print("🎉 Excelente! Todas as ofertas vigentes possuem imagem!")

if __name__ == "__main__":
    try:
        listar_ofertas_sem_imagem()
    except KeyboardInterrupt:
        print("\n\n👋 Operação cancelada pelo usuário.")
        sys.exit(0)
