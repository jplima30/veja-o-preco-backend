import sys
import os
import re
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

def executar_migracao_pets():
    print("=========================================================")
    print("🚀 SCRIPT DE MIGRAÇÃO: CATEGORIA PET")
    print("=========================================================\n")
    
    print("⏳ Carregando catálogo de produtos do Firestore...")
    produtos_ref = db.collection("produtos").stream()
    
    produtos_para_atualizar = []
    
    # Reutiliza a lógica de palavras chaves refinadas de pet
    termos_pet_exatos = [
        r'\bração\b', r'\bracao\b', r'\bcão\b', r'\bcaes\b', r'\bcao\b', r'\bgato\b', r'\bgatos\b', 
        r'\bcachorro\b', r'\bcachorros\b', r'\bfilhote\b', r'\bfilhotes\b', r'\bpedigree\b', 
        r'\bwhiskas\b', r'\bfriskies\b', r'\bpurina\b', r'\bdog chow\b', r'\bcat chow\b', 
        r'\bprocão\b', r'\bprocao\b', r'\bmonello\b', r'\bbirbo\b', r'\bsachê pet\b', r'\bsache pet\b',
        r'\badestrador\b', r'\bshampoo pet\b', r'\bpet care\b', r'\bveterinário\b', r'\bveterinario\b',
        r'\bkdog\b'
    ]
    
    for doc in produtos_ref:
        if doc.id.startswith("_"):
            continue
        d = doc.to_dict()
        nome = d.get("nome", "")
        nome_lower = nome.lower()
        cat_atual = d.get("categoria", "ALIMENTOS")
        
        # Ignorar os falsos humanos comuns
        if any(x in nome_lower for x in ["coração de", "coracao de", "pettiz", "petitiz", "gourmet", "biscoito ao leite", "pão de"]):
            continue
            
        match = False
        for pattern in termos_pet_exatos:
            if re.search(pattern, nome_lower):
                match = True
                break
                
        # Roda a normalizar_categoria para dupla verificação de desvios
        cat_nova = normalizar_categoria(nome)
        
        if (match or cat_nova == "PET") and cat_atual != "PET":
            produtos_para_atualizar.append({
                "id": doc.id,
                "nome": nome,
                "categoria_antiga": cat_atual
            })
            
    print(f"✅ Varredura concluída. Encontrados {len(produtos_para_atualizar)} produtos pet elegíveis para reclassificação.")
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
        cat_antiga = prod["categoria_antiga"]
        
        # 1. Adiciona a atualização do produto no lote
        prod_doc_ref = db.collection("produtos").document(prod_id)
        batch.update(prod_doc_ref, {"categoria": "PET"})
        operacoes_count += 1
        total_produtos += 1
        
        # 2. Busca e adiciona a atualização das ofertas do produto no lote
        ofertas_ref = db.collection("ofertas").where("produto_id", "==", prod_id).stream()
        for of_doc in ofertas_ref:
            batch.update(of_doc.reference, {"categoria": "PET"})
            operacoes_count += 1
            total_ofertas += 1
            
            # Se atingir o limite de 500 escritas do Firestore
            if operacoes_count >= 450:
                print(f"  📤 Enviando lote parcial de escritas ({operacoes_count} operações)...")
                batch.commit()
                batch = db.batch()
                operacoes_count = 0
                time.sleep(1)
                
        if operacoes_count >= 450:
            print(f"  📤 Enviando lote parcial de escritas ({operacoes_count} operações)...")
            batch.commit()
            batch = db.batch()
            operacoes_count = 0
            time.sleep(1)
            
    # Commit final se restarem operações
    if operacoes_count > 0:
        print(f"  📤 Enviando lote final de escritas ({operacoes_count} operações)...")
        batch.commit()
        
    print("\n=========================================================")
    print("🏁 MIGRAÇÃO PET CONCLUÍDA COM SUCESSO!")
    print(f"  * Total de Produtos Reclassificados para PET: {total_produtos}")
    print(f"  * Total de Ofertas Vinculadas Atualizadas: {total_ofertas}")
    print("=========================================================")

if __name__ == "__main__":
    try:
        executar_migracao_pets()
    except KeyboardInterrupt:
        print("\n\n👋 Migração interrompida pelo usuário.")
        sys.exit(0)
