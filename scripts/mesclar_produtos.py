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

def limpar_nome_promocional(nome: str) -> str:
    """
    Remove do nome do produto termos e slogans promocionais como:
    "Leve mais e pague menos", "Leve X pague Y", etc.
    """
    import re
    n = nome.strip()
    # 1. Remove "leve mais e pague menos" / "leve mais pague menos"
    n = re.sub(r'\s*\b(leve\s+mais\s+(e\s+)?pague\s+menos)\b\.?\s*$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\s*\b(leve\s+mais\s+(e\s+)?pague\s+menos)\b\.?\s*', '', n, flags=re.IGNORECASE)
    # 2. Remove "leve X pague Y" (ex: leve 3 pague 2, leve 4 pague 3)
    n = re.sub(r'\s*\b(leve\s+\d+\s+pague\s+\d+)\b\.?\s*$', '', n, flags=re.IGNORECASE)
    # 3. Remove "pague X leve Y" (ex: pague 2 leve 3)
    n = re.sub(r'\s*\b(pague\s+\d+\s+leve\s+\d+)\b\.?\s*$', '', n, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', n).strip()

def mesclar_banco():
    print("=========================================================")
    print("🔄 INICIANDO MESCLAGEM AUTOMÁTICA DE PRODUTOS NO FIRESTORE")
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
        n = limpar_nome_promocional(nome)
        n = re.sub(r'\s*\b(kg|kilo|quilo|un|und|unid|unidade|cada|g|gr|gramas|ml|l|litro|litros)\b\.?\s*$', '', n, flags=re.IGNORECASE)
        
        texto = f"{n} {unidade_norm}".strip().lower()
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
            "nome": limpar_nome_promocional(doc_principal_data.get("nome", "")),
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

def mesclar_manual(id_de: str, id_para: str):
    print("=========================================================")
    print("🔄 INICIANDO MESCLAGEM MANUAL DE PRODUTOS")
    print(f"   👉 De (Duplicado): {id_de}")
    print(f"   👉 Para (Correto): {id_para}")
    print("=========================================================\n")
    
    produtos_ref = db.collection("produtos")
    
    # 1. Carrega os dois produtos
    doc_de = produtos_ref.document(id_de).get()
    doc_para = produtos_ref.document(id_para).get()
    
    if not doc_de.exists:
        print(f"❌ Erro: O produto de origem '{id_de}' não existe no Firestore.")
        return
    if not doc_para.exists:
        print(f"❌ Erro: O produto de destino '{id_para}' não existe no Firestore.")
        return
        
    data_de = doc_de.to_dict()
    data_para = doc_para.to_dict()
    
    # 2. Migrar as ofertas
    print("⏳ Buscando ofertas associadas ao produto duplicado...")
    ofertas_ref = db.collection("ofertas").where("produto_id", "==", id_de).stream()
    ofertas_migradas = 0
    
    unidade_norm = normalizar_unidade(data_para.get("unidade", "un"))
    
    for of_doc in ofertas_ref:
        of_doc.reference.update({
            "produto_id": id_para,
            "unidade": unidade_norm
        })
        ofertas_migradas += 1
        
    # 3. Herdar imagem se o de origem tiver e o destino não
    if data_de.get("imagem_url") and not data_para.get("imagem_url"):
        produtos_ref.document(id_para).update({
            "imagem_url": data_de.get("imagem_url"),
            "imagem_origem": data_de.get("imagem_origem", "manual"),
            "atualizado_em": firestore.SERVER_TIMESTAMP
        })
        print("   🖼️ Herdada imagem do duplicado para o principal.")
        
    # 4. Deleta o produto duplicado
    produtos_ref.document(id_de).delete()
    
    print("\n=========================================================")
    print("🏁 CONCLUÍDO COM SUCESSO!")
    print(f"📉 Produto duplicado '{id_de}' deletado.")
    print(f"🔄 Total de ofertas re-vinculadas para '{id_para}': {ofertas_migradas}")
    print("=========================================================\n")

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            if "--de" in sys.argv and "--para" in sys.argv:
                try:
                    idx_de = sys.argv.index("--de") + 1
                    idx_para = sys.argv.index("--para") + 1
                    id_de = sys.argv[idx_de]
                    id_para = sys.argv[idx_para]
                    mesclar_manual(id_de, id_para)
                except IndexError:
                    print("❌ Erro: Especifique os IDs após --de e --para.")
                    print("Exemplo: python3 mesclar_produtos.py --de id-com-erro --para id-correto")
            else:
                print("❌ Argumentos inválidos.")
                print("Uso:")
                print("  Automático: python3 mesclar_produtos.py")
                print("  Manual:     python3 mesclar_produtos.py --de ID_RUIM --para ID_BOM")
        else:
            mesclar_banco()
    except KeyboardInterrupt:
        print("\n\n👋 Operação cancelada pelo usuário.")
        sys.exit(0)
