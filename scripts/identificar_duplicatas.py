import os
import sys

# Adiciona as pastas corretas ao Path para importação do Firebase Admin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore

if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
db = firestore.client()

def extrair_numeros(nome: str) -> list:
    import re
    # Encontra sequências de números no nome (ex: 200g -> ['200'])
    return re.findall(r'\d+', nome.lower())

def obter_similaridade(n1: str, n2: str, w1: set, w2: set) -> tuple:
    import difflib
    # 1. Similaridade Direta (Fuzzy Levenshtein-like)
    raz_direta = difflib.SequenceMatcher(None, n1, n2).ratio()
    
    # 2. Similaridade por Token Sort (Ordem das palavras)
    t1 = " ".join(sorted(n1.split()))
    t2 = " ".join(sorted(n2.split()))
    raz_token = difflib.SequenceMatcher(None, t1, t2).ratio()
    
    # 3. Overlap de Palavras (Inclusão)
    if w1 and w2:
        intersec = w1.intersection(w2)
        min_words = min(len(w1), len(w2))
        overlap = len(intersec) / min_words if min_words > 0 else 0
        diff_tamanho = abs(len(w1) - len(w2))
    else:
        overlap = 0
        diff_tamanho = 99
        
    return raz_direta, raz_token, overlap, diff_tamanho

def buscar_duplicatas_potenciais() -> list:
    """
    Varre o Firestore, aplica a heurística e retorna lista de tuplas de duplicatas:
    [(prod_a_id, prod_a_data, prod_b_id, prod_b_data, razao_max)]
    """
    produtos_ref = db.collection("produtos")
    docs = list(produtos_ref.stream())
    
    produtos = []
    for d in docs:
        data = d.to_dict()
        nome = data.get("nome", "")
        # Precomputa em minúsculo
        nome_limpo = nome.lower().strip()
        nums = extrair_numeros(nome_limpo)
        words = set(nome_limpo.split())
        produtos.append((d.id, data, nome_limpo, nums, words))
        
    duplicatas = []
    total = len(produtos)
    
    # Loops aninhados otimizados
    for i in range(total):
        id_a, data_a, name_a, nums_a, words_a = produtos[i]
        
        for j in range(i + 1, total):
            id_b, data_b, name_b, nums_b, words_b = produtos[j]
            
            # Heurística rápida 1: Se os números forem diferentes (ex: 200g vs 395g), pula
            if nums_a != nums_b:
                continue
                
            # Calcula similaridades
            raz_direta, raz_token, overlap, diff_tamanho = obter_similaridade(name_a, name_b, words_a, words_b)
            
            # Condição de correspondência
            eh_duplicata = False
            razao_max = max(raz_direta, raz_token)
            
            # Se a similaridade ortográfica for alta
            if razao_max >= 0.85:
                eh_duplicata = True
            # Se for uma substring quase total com diferença de tamanho de até 2 palavras
            # Restringido a nomes que tenham pelo menos 3 palavras para evitar falsos positivos
            # (Ex: evita casar "Alho" com "Alho Roxo" ou "Abacaxi" com "Abacaxi Hawai")
            elif min(len(words_a), len(words_b)) >= 3 and overlap >= 0.80 and diff_tamanho <= 2:
                eh_duplicata = True
                razao_max = overlap
                
            if eh_duplicata:
                duplicatas.append((id_a, data_a, id_b, data_b, razao_max))
                
    # Ordena as duplicatas encontradas por maior similaridade
    duplicatas.sort(key=lambda x: x[4], reverse=True)
    return duplicatas

def mesclar_produtos_firestore(id_de: str, id_para: str) -> bool:
    produtos_ref = db.collection("produtos")
    
    doc_de = produtos_ref.document(id_de).get()
    doc_para = produtos_ref.document(id_para).get()
    
    if not doc_de.exists or not doc_para.exists:
        return False
        
    data_de = doc_de.to_dict()
    data_para = doc_para.to_dict()
    
    # 1. Migrar ofertas
    ofertas_ref = db.collection("ofertas").where("produto_id", "==", id_de).stream()
    ofertas_migradas = 0
    unidade_norm = data_para.get("unidade", "un")
    
    for of_doc in ofertas_ref:
        of_doc.reference.update({
            "produto_id": id_para,
            "unidade": unidade_norm
        })
        ofertas_migradas += 1
        
    # 2. Herdar imagem se o de origem tiver e o destino não
    if data_de.get("imagem_url") and not data_para.get("imagem_url"):
        produtos_ref.document(id_para).update({
            "imagem_url": data_de.get("imagem_url"),
            "imagem_origem": data_de.get("imagem_origem", "manual"),
            "atualizado_em": firestore.SERVER_TIMESTAMP
        })
        
    # 3. Deleta duplicado
    produtos_ref.document(id_de).delete()
    return True

def rodar_diagnostico_cron():
    print("⏳ Analisando integridade do catálogo por similaridade...")
    try:
        duplicatas = buscar_duplicatas_potenciais()
        if not duplicatas:
            print("✨ INTEGRIDADE: Nenhuma duplicata em potencial detectada no banco de dados!")
            return
            
        print("\n" + "!" * 60)
        print(f"⚠️  ALERTA: ENCONTRADAS {len(duplicatas)} POTENCIAIS DUPLICATAS NO BANCO:")
        print("!" * 60)
        
        # Agrupa e mostra os top 10 potenciais duplicados
        contador = 0
        for id_a, data_a, id_b, data_b, score in duplicatas:
            contador += 1
            print(f"  • [{score*100:.1f}%] '{data_a.get('nome')}' ↔️ '{data_b.get('nome')}'")
            print(f"    IDs: {id_a} ↔️ {id_b}")
            if contador >= 10:
                print(f"  ... e mais {len(duplicatas) - 10} potenciais correspondências.")
                break
                
        print("\n💡 Dica: Rode `python3 scripts/gerenciador.py` e escolha a opção 4 -> 3")
        print("   para resolver estas duplicidades de forma guiada no terminal.")
        print("="*60 + "\n")
    except Exception as e:
        print(f"⚠️ Falha ao rodar diagnóstico de duplicatas: {e}")

def rodar_assistente_interativo():
    print("=========================================================")
    print("🔍 ASSISTENTE DE DUPLICATAS POTENCIAIS (FUZZY MATCHING)")
    print("=========================================================")
    print("⏳ Buscando duplicatas potenciais no Firestore...")
    
    try:
        duplicatas = buscar_duplicatas_potenciais()
    except Exception as e:
        print(f"❌ Erro ao ler produtos: {e}")
        input("\nPressione Enter para voltar...")
        return
        
    if not duplicatas:
        print("\n✨ Parabéns! Nenhuma duplicata em potencial encontrada no banco.")
        input("\nPressione Enter para voltar...")
        return
        
    total = len(duplicatas)
    atual = 0
    
    while atual < total:
        id_a, data_a, id_b, data_b, score = duplicatas[atual]
        
        # Recarrega o estado caso tenham sido apagados em passos anteriores
        doc_a = db.collection("produtos").document(id_a).get()
        doc_b = db.collection("produtos").document(id_b).get()
        
        if not doc_a.exists or not doc_b.exists:
            # Um deles já foi mesclado ou excluído em lote, passa adiante
            atual += 1
            continue
            
        data_a = doc_a.to_dict()
        data_b = doc_b.to_dict()
        
        os.system("clear")
        print(f"=========================================================")
        print(f"⚠️  POTENCIAL DUPLICATA ({atual + 1}/{total}) - SCORE: {score*100:.1f}%")
        print(f"=========================================================")
        
        has_img_a = "✅ Sim" if data_a.get("imagem_url") else "❌ Não"
        has_img_b = "✅ Sim" if data_b.get("imagem_url") else "❌ Não"
        
        print(f" [A] ID: {id_a}")
        print(f"     Nome:   {data_a.get('nome')} ({data_a.get('unidade')})")
        print(f"     Imagem: [{has_img_a}]")
        print("-" * 57)
        print(f" [B] ID: {id_b}")
        print(f"     Nome:   {data_b.get('nome')} ({data_b.get('unidade')})")
        print(f"     Imagem: [{has_img_b}]")
        print("=========================================================")
        print(" O que deseja fazer?")
        print("   [1] Sim, mesclar B para A (Mantém o item [A])")
        print("   [2] Sim, mesclar A para B (Mantém o item [B])")
        print("   [3] Ignorar este par e ir para o próximo")
        print("   [0] Sair do assistente")
        print("=========================================================")
        
        opcao = input("👉 Escolha uma opção [0-3]: ").strip()
        
        if opcao == "0":
            break
        elif opcao == "1":
            print(f"\n⏳ Mesclando '{id_b}' em '{id_a}'...")
            if mesclar_produtos_firestore(id_b, id_a):
                print("✅ Mesclado com sucesso!")
            else:
                print("❌ Falha ao mesclar.")
            time.sleep(1)
            atual += 1
        elif opcao == "2":
            print(f"\n⏳ Mesclando '{id_a}' em '{id_b}'...")
            if mesclar_produtos_firestore(id_a, id_b):
                print("✅ Mesclado com sucesso!")
            else:
                print("❌ Falha ao mesclar.")
            time.sleep(1)
            atual += 1
        elif opcao == "3":
            atual += 1
        else:
            print("⚠️ Opção inválida.")
            time.sleep(1)

    print("\n👋 Assistente finalizado.")
    input("Pressione Enter para voltar ao menu...")

if __name__ == "__main__":
    import time
    if "--detect-only" in sys.argv:
        rodar_diagnostico_cron()
    else:
        rodar_assistente_interativo()
