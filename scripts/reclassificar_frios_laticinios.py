import sys
import os
import time

# Adiciona as pastas corretas ao Path para importações
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore
from functions.main import normalizar_categoria

# Inicializa Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})

db = firestore.client()

def executar_migracao():
    print("=========================================================")
    print("🚀 SCRIPT DE MIGRAÇÃO: CATEGORIA FRIOS_LATICINIOS")
    print("=========================================================\n")
    
    print("⏳ Carregando catálogo de produtos do Firestore...")
    produtos_ref = db.collection("produtos").stream()
    
    produtos_para_atualizar = []
    
    # 1. Identifica quais produtos devem ser reclassificados
    for doc in produtos_ref:
        if doc.id.startswith("_"):
            continue
        d = doc.to_dict()
        nome = d.get("nome", "")
        cat_atual = d.get("categoria", "ALIMENTOS")
        
        # Roda a função de normalização atualizada para obter a categoria correta
        cat_nova = normalizar_categoria(nome)
        
        if cat_nova == "FRIOS_LATICINIOS" and cat_atual != "FRIOS_LATICINIOS":
            produtos_para_atualizar.append({
                "id": doc.id,
                "nome": nome,
                "categoria_antiga": cat_atual
            })
            
    print(f"✅ Varredura concluída. Encontrados {len(produtos_para_atualizar)} produtos elegíveis para reclassificação.")
    if not produtos_para_atualizar:
        print("✨ Nenhum produto precisa ser migrado no momento!")
        return
        
    print("\n📦 Iniciando gravação em lotes (WriteBatch) no Firestore...")
    
    batch = db.batch()
    operacoes_count = 0
    total_produtos = 0
    total_ofertas = 0
    
    for idx, prod in enumerate(produtos_para_atualizar):
        prod_id = prod["id"]
        nome = prod["nome"]
        
        # 1. Adiciona a atualização do produto no lote
        prod_doc_ref = db.collection("produtos").document(prod_id)
        batch.update(prod_doc_ref, {"categoria": "FRIOS_LATICINIOS"})
        operacoes_count += 1
        total_produtos += 1
        
        # 2. Busca e adiciona a atualização das ofertas do produto no lote
        ofertas_ref = db.collection("ofertas").where("produto_id", "==", prod_id).stream()
        for of_doc in ofertas_ref:
            batch.update(of_doc.reference, {"categoria": "FRIOS_LATICINIOS"})
            operacoes_count += 1
            total_ofertas += 1
            
            # Se atingir o limite seguro do Firestore de 500 escritas num único batch
            if operacoes_count >= 450:
                print(f"  📤 Enviando lote parcial de escritas ({operacoes_count} operações)...")
                batch.commit()
                batch = db.batch()
                operacoes_count = 0
                time.sleep(1) # Delay preventivo para taxas
                
        # Se as operações acumuladas com o produto passarem de 450
        if operacoes_count >= 450:
            print(f"  📤 Enviando lote parcial de escritas ({operacoes_count} operações)...")
            batch.commit()
            batch = db.batch()
            operacoes_count = 0
            time.sleep(1)
            
    # Commit final se restarem operações no batch
    if operacoes_count > 0:
        print(f"  📤 Enviando lote final de escritas ({operacoes_count} operações)...")
        batch.commit()
        
    print("\n=========================================================")
    print("🏁 MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
    print(f"  * Total de Produtos Reclassificados: {total_produtos}")
    print(f"  * Total de Ofertas Vinculadas Atualizadas: {total_ofertas}")
    print("=========================================================")

if __name__ == "__main__":
    try:
        executar_migracao()
    except KeyboardInterrupt:
        print("\n\n👋 Migração interrompida pelo usuário.")
        sys.exit(0)
