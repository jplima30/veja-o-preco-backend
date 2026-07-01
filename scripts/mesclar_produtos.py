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

def normalizar_unidade(unidade: str) -> str:
    u = unidade.strip().lower()
    if u in ("cada", "unidade", "unid", "und", "un"):
        return "un"
    if u in ("quilo", "kilo", "kg"):
        return "kg"
    if u in ("litro", "litros", "l"):
        return "l"
    if u in ("grama", "gramas", "gr", "g"):
        return "g"
    return u

def mesclar_banco():
    print("=========================================================")
    print("🔄 INICIANDO MESCLAGEM DE PRODUTOS DUPLICADOS NO FIRESTORE")
    print("=========================================================\n")
    
    print("⏳ Carregando produtos...")
    produtos_ref = db.collection("produtos")
    produtos = list(produtos_ref.stream())
    print(f"✅ {len(produtos)} produtos carregados.")
    
    # 1. Agrupar produtos pelo ID normalizado correto
    mapa_unificado = {} # id_correto -> lista de (doc_id, doc_data)
    
    for p_doc in produtos:
        d = p_doc.to_dict()
        nome = d.get("nome", "")
        unidade = d.get("unidade", "")
        
        # Gera o ID unificado correto
        unidade_norm = normalizar_unidade(unidade)
        
        # Código idêntico a normalizar_nome do main.py para consistência de ID
        import re
        texto = f"{nome} {unidade_norm}".strip().lower()
        texto = re.sub(r'[áàãâä]', 'a', texto)
        texto = re.sub(r'[éèêë]', 'e', texto)
        texto = re.sub(r'[íìîï]', 'i', texto)
        texto = re.sub(r'[óòõôö]', 'o', texto)
        texto = re.sub(r'[úùûü]', 'u', texto)
        texto = re.sub(r'[ç]', 'c', texto)
        texto = re.sub(r'[^a-z0-9\s]', '', texto)
        id_correto = re.sub(r'\s+', '-', texto.strip())
        
        if id_correto not in mapa_unificado:
            mapa_unificado[id_correto] = []
        mapa_unificado[id_correto].append((p_doc.id, d))
        
    print(f"✅ Processamento concluído. {len(mapa_unificado)} produtos únicos mapeados.")
    
    total_deletados = 0
    total_mesclados = 0
    
    # 2. Identificar grupos de duplicados e realizar a mesclagem
    for id_correto, duplicados in mapa_unificado.items():
        if len(duplicados) <= 1:
            continue
            
        # Dentre os duplicados, vamos preferir como principal:
        # A) Aquele cujo ID é exatamente igual a id_correto (ID padrão).
        # B) Se nenhum for, aquele que possui imagem_url preenchida.
        # C) Caso contrário, o primeiro.
        
        doc_principal_id = None
        doc_principal_data = None
        
        # Tenta achar o id_correto exato
        for doc_id, d in duplicados:
            if doc_id == id_correto:
                doc_principal_id = doc_id
                doc_principal_data = d
                break
                
        # Se não achou, pega o que tem imagem
        if not doc_principal_id:
            for doc_id, d in duplicados:
                if d.get("imagem_url"):
                    doc_principal_id = doc_id
                    doc_principal_data = d
                    break
                    
        # Se ainda não, pega o primeiro
        if not doc_principal_id:
            doc_principal_id, doc_principal_data = duplicados[0]
            
        # Para todos os OUTROS duplicados, migramos as ofertas e depois deletamos
        outros = [item for item in duplicados if item[0] != doc_principal_id]
        
        print(f"\n🔄 Mesclando variações para o produto: '{doc_principal_data.get('nome')}'")
        print(f"   👑 Principal: {doc_principal_id} ({doc_principal_data.get('unidade')})")
        
        # Garante que a unidade do principal seja normalizada no banco
        unidade_principal_norm = normalizar_unidade(doc_principal_data.get("unidade", "un"))
        produtos_ref.document(doc_principal_id).update({
            "unidade": unidade_principal_norm
        })
        
        for doc_id_velho, d_velho in outros:
            print(f"   ❌ Duplicado a remover: {doc_id_velho} ({d_velho.get('unidade')})")
            
            # Buscar todas as ofertas ligadas ao id_velho
            ofertas_ref = db.collection("ofertas").where("produto_id", "==", doc_id_velho).stream()
            ofertas_migradas = 0
            for of_doc in ofertas_ref:
                # Atualizar produto_id e unidade da oferta
                of_doc.reference.update({
                    "produto_id": doc_principal_id,
                    "unidade": unidade_principal_norm
                })
                ofertas_migradas += 1
                
            # Se o documento velho tiver imagem e o principal não tiver, herda a imagem!
            if d_velho.get("imagem_url") and not doc_principal_data.get("imagem_url"):
                doc_principal_data["imagem_url"] = d_velho.get("imagem_url")
                doc_principal_data["imagem_origem"] = d_velho.get("imagem_origem")
                
                produtos_ref.document(doc_principal_id).update({
                    "imagem_url": d_velho.get("imagem_url"),
                    "imagem_origem": d_velho.get("imagem_origem")
                })
                print("   🖼️ Herdada imagem do duplicado.")
                
            # Deletar o produto duplicado do Firestore
            produtos_ref.document(doc_id_velho).delete()
            
            total_deletados += 1
            total_mesclados += ofertas_migradas
            print(f"     ✅ Migradas {ofertas_migradas} ofertas e deletado o produto secundário.")
            
    print("\n=========================================================")
    print("🏁 CONCLUÍDO!")
    print(f"📉 Total de produtos duplicados deletados: {total_deletados}")
    print(f"🔄 Total de ofertas re-vinculadas: {total_mesclados}")
    print("=========================================================\n")

if __name__ == "__main__":
    try:
        mesclar_banco()
    except KeyboardInterrupt:
        print("\n\n👋 Operação cancelada pelo usuário.")
        sys.exit(0)
