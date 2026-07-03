import firebase_admin
from firebase_admin import firestore
import re

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()

def classificar_refinado(nome, cat_original):
    nome_lower = nome.lower()
    cat_original_lower = cat_original.lower()
    
    # 1. Regra de Higiene / Limpeza baseadas na categoria original do banco
    if any(x in cat_original_lower for x in ["limpeza", "detergente", "sabão", "sabao"]):
        return "LIMPEZA"
    if any(x in cat_original_lower for x in ["higiene", "perfumaria", "cosmético", "cosmetico", "shampoo", "sabonete"]):
        return "HIGIENE"

    # Exclusões de produtos industrializados/mercearia para evitar falsos positivos
    if any(term in nome_lower for term in ["farofa", "extrato", "molho", "sachê", "sache", "tempero", "caldo", "conserva", "ração", "racao"]):
        return "ALIMENTOS"

    # 2. BEBIDAS (Avaliar antes de Hortifruti para evitar que suco de uva vire Hortifruti)
    termos_bebidas = [
        "refrigerante", "coca-cola", "coca cola", "fanta", "guaraná", "guarana", "suco", 
        "del valle", "ades", "red bull", "monster", "bebida láctea", "bebida lactea", "gatorade", 
        "água mineral", "agua mineral", "h2oh", "tônica", "tonica"
    ]
    if any(re.search(rf'\b{term}\b', nome_lower) for term in termos_bebidas):
        if "lámen" in nome_lower or "lamen" in nome_lower or "miojo" in nome_lower:
            return "ALIMENTOS"
        return "BEBIDAS"

    # 3. CARNES
    termos_carnes = [
        "carne", "picanha", "alcatra", "músculo", "musculo", "peito de frango", "sobrecoxa", 
        "asa", "coração", "coracao", "linguiça", "linguica", "salsicha", "tambaqui", "peixe", 
        "filé", "file", "bovino", "suíno", "suino", "frango", "bacalhau", "salame", "mortadela",
        "presunto", "costelinha", "chouriço", "chourico", "pernil", "paleta"
    ]
    if any(re.search(rf'\b{term}\b', nome_lower) for term in termos_carnes):
        if "ração" in nome_lower or "racao" in nome_lower:
            return "ALIMENTOS"
        return "CARNES"
        
    # 4. HORTIFRUTI
    termos_horti = [
        "limão", "limao", "banana", "maçã", "maca", "uva", "abacaxi", "mamão", "mamao", 
        "laranja", "cebola", "alho", "tomate", "batata", "cenoura", "ovos", "ovo", "cheiro verde", 
        "coentro", "pimentão", "pimentao", "abóbora", "abobora", "morango", "melancia", 
        "alface", "repolho", "coentro", "cheiro-verde", "cebolinha"
    ]
    if any(re.search(rf'\b{term}\b', nome_lower) for term in termos_horti):
        return "HORTIFRUTI"
        
    # 5. PADARIA
    termos_padaria = [
        "pão", "pao", "bisnaguinha", "bolo", "torta", "torrada", "croissant", 
        "pão de queijo", "pao de queijo", "brioche", "cookie", "donuts"
    ]
    if any(re.search(rf'\b{term}\b', nome_lower) for term in termos_padaria):
        if "bolota" in nome_lower:
            return "ALIMENTOS"
        return "PADARIA"
        
    if re.search(r'\bsalgado\b', nome_lower):
        if not any(x in nome_lower for x in ["amendoim", "camarão", "camarao", "peixe", "castanha"]):
            return "PADARIA"
            
    # 6. HIGIENE
    termos_higiene = [
        "shampoo", "sabonete", "creme dental", "pasta de dente", "colgate", "sensodyne", 
        "fio dental", "desodorante", "rexona", "nivea", "dove", "absorvente", "fralda", 
        "condicionador", "hidratante", "protetor solar", "óleo capilar", "oleo capilar", 
        "tintura", "maxton", "aparelho de barbear", "gillette", "listerine", "colônia", "colonia", "esmalte"
    ]
    if any(re.search(rf'\b{term}\b', nome_lower) for term in termos_higiene):
        return "HIGIENE"

    # 7. LIMPEZA
    termos_limpeza = [
        "detergente", "sabão", "sabao", "amaciante", "desinfetante", "lava-louças", "lavaloucas", 
        "clorox", "veja", "ypê", "ype", "omo", "brilhante", "tixan", "downy", "comfort", 
        "papel higiênico", "papel higienico", "esponja", "lã de aço", "la de aco", "bombril"
    ]
    if any(re.search(rf'\b{term}\b', nome_lower) for term in termos_limpeza):
        return "LIMPEZA"

    return "ALIMENTOS"

def migrar_colecao(nome_colecao, campo_nome):
    print(f"🚀 Iniciando migração da coleção '{nome_colecao}'...")
    ref = db.collection(nome_colecao).stream()
    batch = db.batch()
    count = 0
    total_atualizados = 0

    for doc in ref:
        d = doc.to_dict()
        nome = d.get(campo_nome, '')
        cat_orig = d.get('categoria', 'ALIMENTOS') or 'ALIMENTOS'
        
        cat_nova = classificar_refinado(nome, cat_orig)
        
        if cat_nova != cat_orig:
            batch.update(doc.reference, {"categoria": cat_nova})
            count += 1
            total_atualizados += 1
            print(f"  📝 [{total_atualizados}] ID: {doc.id} | {nome[:40]} -> {cat_orig} ===> {cat_nova}")
            
            if count == 500:
                print("⏳ Enviando lote de 500 escritas ao Firestore...")
                batch.commit()
                batch = db.batch()
                count = 0

    if count > 0:
        print(f"⏳ Enviando lote final de {count} escritas ao Firestore...")
        batch.commit()

    print(f"✅ Coleção '{nome_colecao}' concluída! Total de {total_atualizados} documentos modificados.\n")

if __name__ == "__main__":
    # 1. Atualizar ofertas
    migrar_colecao("ofertas", "produto_nome")
    # 2. Atualizar produtos
    migrar_colecao("produtos", "nome")
    print("🎉 Migração de categorias concluída com sucesso!")
