import os
import sys
from datetime import datetime

# Adiciona as pastas corretas ao Path para importação do Firebase Admin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore

if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
db = firestore.client()

MAP_SUPERMERCADOS = {
    "assai": "Assaí",
    "lider": "Líder",
    "formosa": "Formosa",
    "guerreirao": "Guerreirão",
    "mateus": "Mix Mateus",
    "atacadao": "Atacadão",
    "economico": "Seja Econômico"
}


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
    # Carrega duplicatas ignoradas para filtrar do escaneamento
    ignorados_ref = db.collection("duplicatas_ignoradas")
    ignorados_docs = list(ignorados_ref.stream())
    pares_ignorados = {doc.id for doc in ignorados_docs}

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
            
            # Filtro de ignorados (ordena alfabeticamente para a chave única)
            chave_ignorado = f"{id_a}_vs_{id_b}" if id_a < id_b else f"{id_b}_vs_{id_a}"
            if chave_ignorado in pares_ignorados:
                continue

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
    
    # 4. Registrar sinônimo para redirecionamento futuro
    db.collection("sinonimos").document(id_de).set({
        "id_correto": id_para,
        "criado_em": firestore.SERVER_TIMESTAMP
    })
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
        
        n1 = data_a.get("nome", "").lower().strip()
        n2 = data_b.get("nome", "").lower().strip()
        w1 = set(n1.split())
        w2 = set(n2.split())
        
        import difflib
        raz_direta = difflib.SequenceMatcher(None, n1, n2).ratio()
        t1 = " ".join(sorted(n1.split()))
        t2 = " ".join(sorted(n2.split()))
        raz_token = difflib.SequenceMatcher(None, t1, t2).ratio()
        
        intersec = w1.intersection(w2)
        min_words = len(w1) if len(w1) < len(w2) else len(w2)
        overlap = len(intersec) / min_words if min_words > 0 else 0
        
        # Busca lojas das ofertas (vigentes e histórico) para A
        lojas_a_ativas = []
        lojas_a_historico = []
        try:
            ofs_a = db.collection("ofertas").where("produto_id", "==", id_a).stream()
            hoje = datetime.now()
            for of in ofs_a:
                o_data = of.to_dict()
                
                # Resolução inteligente do nome da loja caso venha genérico como "Extração via Visão (IA)"
                loja_nome = o_data.get("loja", "Desconhecida")
                if "visão" in loja_nome.lower() or "visao" in loja_nome.lower() or not loja_nome:
                    super_id = o_data.get("supermercado_id", "")
                    loja_nome = MAP_SUPERMERCADOS.get(super_id, super_id.upper() or "Desconhecida")
                
                expira_em = o_data.get("expira_em")
                if expira_em:
                    expira_naive = expira_em.replace(tzinfo=None) if hasattr(expira_em, "tzinfo") and expira_em.tzinfo else expira_em
                    if expira_naive >= hoje:
                        lojas_a_ativas.append(loja_nome)
                    else:
                        lojas_a_historico.append(f"{loja_nome} (Histórico)")
                else:
                    lojas_a_historico.append(f"{loja_nome} (Histórico)")
            lojas_a_ativas = sorted(list(set(lojas_a_ativas)))
            lojas_a_historico = sorted(list(set(lojas_a_historico)))
        except Exception:
            pass
            
        # Determina o display para A
        if lojas_a_ativas:
            lojas_a_str = ", ".join(lojas_a_ativas)
        elif lojas_a_historico:
            lojas_a_str = ", ".join(lojas_a_historico)
        else:
            # Tenta ler o campo de origem definitiva do produto
            origem_id = data_a.get("supermercado_origem", "")
            if origem_id:
                origem_nome = MAP_SUPERMERCADOS.get(origem_id, origem_id.upper())
                lojas_a_str = f"[Sem ofertas] (Origem: {origem_nome})"
            else:
                lojas_a_str = "[Sem ofertas]"
            
        # Busca lojas das ofertas (vigentes e histórico) para B
        lojas_b_ativas = []
        lojas_b_historico = []
        try:
            ofs_b = db.collection("ofertas").where("produto_id", "==", id_b).stream()
            hoje = datetime.now()
            for of in ofs_b:
                o_data = of.to_dict()
                
                # Resolução inteligente do nome da loja caso venha genérico como "Extração via Visão (IA)"
                loja_nome = o_data.get("loja", "Desconhecida")
                if "visão" in loja_nome.lower() or "visao" in loja_nome.lower() or not loja_nome:
                    super_id = o_data.get("supermercado_id", "")
                    loja_nome = MAP_SUPERMERCADOS.get(super_id, super_id.upper() or "Desconhecida")
                
                expira_em = o_data.get("expira_em")
                if expira_em:
                    expira_naive = expira_em.replace(tzinfo=None) if hasattr(expira_em, "tzinfo") and expira_em.tzinfo else expira_em
                    if expira_naive >= hoje:
                        lojas_b_ativas.append(loja_nome)
                    else:
                        lojas_b_historico.append(f"{loja_nome} (Histórico)")
                else:
                    lojas_b_historico.append(f"{loja_nome} (Histórico)")
            lojas_b_ativas = sorted(list(set(lojas_b_ativas)))
            lojas_b_historico = sorted(list(set(lojas_b_historico)))
        except Exception:
            pass
            
        # Determina o display para B
        if lojas_b_ativas:
            lojas_b_str = ", ".join(lojas_b_ativas)
        elif lojas_b_historico:
            lojas_b_str = ", ".join(lojas_b_historico)
        else:
            # Tenta ler o campo de origem definitiva do produto
            origem_id = data_b.get("supermercado_origem", "")
            if origem_id:
                origem_nome = MAP_SUPERMERCADOS.get(origem_id, origem_id.upper())
                lojas_b_str = f"[Sem ofertas] (Origem: {origem_nome})"
            else:
                lojas_b_str = "[Sem ofertas]"
            
        os.system("clear")
        print(f"=========================================================")
        print(f"⚠️  POTENCIAL DUPLICATA ({atual + 1}/{total})")
        print(f"   Similaridade: {max(raz_direta, raz_token)*100:.1f}% | Overlap: {overlap*100:.1f}%")
        print(f"=========================================================")
        
        img_url_a = data_a.get("imagem_url", "")
        img_url_b = data_b.get("imagem_url", "")
        
        print(f" [A] ID: {id_a}")
        print(f"     Nome:   {data_a.get('nome')} ({data_a.get('unidade')})")
        print(f"     Lojas:  {lojas_a_str}")
        print(f"     Foto:   [✅ Sim] ({img_url_a})" if img_url_a else "     Foto:   [❌ Não]")
        print("-" * 57)
        print(f" [B] ID: {id_b}")
        print(f"     Nome:   {data_b.get('nome')} ({data_b.get('unidade')})")
        print(f"     Lojas:  {lojas_b_str}")
        print(f"     Foto:   [✅ Sim] ({img_url_b})" if img_url_b else "     Foto:   [❌ Não]")
        print("=========================================================")
        print(" O que deseja fazer?")
        print("   [1] Sim, mesclar B para A (Mantém o item [A])")
        print("   [2] Sim, mesclar A para B (Mantém o item [B])")
        print("   [3] Ignorar este par e ir para o próximo")
        print("   [4] ⚡ Executar mesclagem automática para todas as palavras idênticas")
        print("   [0] Sair do assistente")
        print("=========================================================")
        
        opcao = input("👉 Escolha uma opção [0-4]: ").strip()
        
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
            print(f"\n⏳ Registrando este par como falso positivo ignorado...")
            chave_ignorado = f"{id_a}_vs_{id_b}" if id_a < id_b else f"{id_b}_vs_{id_a}"
            try:
                db.collection("duplicatas_ignoradas").document(chave_ignorado).set({
                    "ignorado": True,
                    "atualizado_em": firestore.SERVER_TIMESTAMP
                })
                print("✅ Par ignorado permanentemente!")
            except Exception as e:
                print(f"⚠️ Erro ao salvar ignorados: {e}")
            time.sleep(1)
            atual += 1
        elif opcao == "4":
            print("\n=========================================================")
            print("🔄 INICIANDO MESCLAGEM AUTOMÁTICA EM LOTE...")
            print("=========================================================")
            total_mesclados = 0
            ids_removidos = set()
            
            for idx_check in range(atual, total):
                id_a_ch, data_a_ch, id_b_ch, data_b_ch, score_ch = duplicatas[idx_check]
                if id_a_ch in ids_removidos or id_b_ch in ids_removidos:
                    continue
                    
                n1 = data_a_ch.get("nome", "").lower().strip()
                n2 = data_b_ch.get("nome", "").lower().strip()
                
                w1 = sorted(n1.split())
                w2 = sorted(n2.split())
                
                if w1 != w2:
                    continue
                    
                has_img_a = bool(data_a_ch.get("imagem_url"))
                has_img_b = bool(data_b_ch.get("imagem_url"))
                
                if has_img_a and not has_img_b:
                    id_manter = id_a_ch
                    id_deletar = id_b_ch
                elif has_img_b and not has_img_a:
                    id_manter = id_b_ch
                    id_deletar = id_a_ch
                else:
                    if id_a_ch <= id_b_ch:
                        id_manter = id_a_ch
                        id_deletar = id_b_ch
                    else:
                        id_manter = id_b_ch
                        id_deletar = id_a_ch
                        
                print(f"🔀 Auto-mesclando: '{id_deletar}' ➡️ '{id_manter}'")
                try:
                    if mesclar_produtos_firestore(id_deletar, id_manter):
                        ids_removidos.add(id_deletar)
                        total_mesclados += 1
                except Exception as e:
                    print(f"   ❌ Erro: {e}")
            
            print(f"\n✨ Concluído! {total_mesclados} duplicatas exatas resolvidas.")
            print("⏳ Recarregando lista de duplicatas do Firestore...")
            time.sleep(2)
            
            try:
                duplicatas = buscar_duplicatas_potenciais()
                total = len(duplicatas)
                atual = 0
            except Exception as e:
                print(f"❌ Erro ao recarregar: {e}")
                input("Pressione Enter para continuar...")
                break
                
            if not duplicatas:
                print("\n✨ Nenhuma duplicata restante encontrada!")
                input("Pressione Enter para continuar...")
                break
        else:
            print("⚠️ Opção inválida.")
            time.sleep(1)

    print("\n👋 Assistente finalizado.")
    input("Pressione Enter para voltar ao menu...")

def rodar_mesclagem_automatica_exata(silent=False):
    print("=========================================================")
    print("🔄 INICIANDO MESCLAGEM AUTOMÁTICA DE PALAVRAS IDÊNTICAS")
    print("=========================================================")
    print("⏳ Carregando produtos e calculando similaridades...")
    try:
        duplicatas = buscar_duplicatas_potenciais()
    except Exception as e:
        print(f"❌ Erro ao ler produtos: {e}")
        if not silent:
            input("\nPressione Enter para continuar...")
        return
        
    if not duplicatas:
        print("\n✨ Nenhuma duplicata potencial encontrada no banco.")
        if not silent:
            input("\nPressione Enter para continuar...")
        return
        
    total_mesclados = 0
    ids_removidos = set()
    
    for id_a, data_a, id_b, data_b, score in duplicatas:
        if id_a in ids_removidos or id_b in ids_removidos:
            continue
            
        n1 = data_a.get("nome", "").lower().strip()
        n2 = data_b.get("nome", "").lower().strip()
        
        w1 = sorted(n1.split())
        w2 = sorted(n2.split())
        
        if w1 != w2:
            continue
            
        has_img_a = bool(data_a.get("imagem_url"))
        has_img_b = bool(data_b.get("imagem_url"))
        
        if has_img_a and not has_img_b:
            id_manter = id_a
            id_deletar = id_b
        elif has_img_b and not has_img_a:
            id_manter = id_b
            id_deletar = id_a
        else:
            if id_a <= id_b:
                id_manter = id_a
                id_deletar = id_b
            else:
                id_manter = id_b
                id_deletar = id_a
                
        print(f"🔀 Mesclando automaticamente: '{id_deletar}' ➡️ '{id_manter}'")
        try:
            if mesclar_produtos_firestore(id_deletar, id_manter):
                ids_removidos.add(id_deletar)
                total_mesclados += 1
            else:
                print(f"   ⚠️ Falha ao mesclar '{id_deletar}'")
        except Exception as e:
            print(f"   ❌ Erro ao mesclar '{id_deletar}': {e}")
            
    print("\n=========================================================")
    print("🏁 MESCLAGEM AUTOMÁTICA CONCLUÍDA!")
    print(f"📉 Total de duplicatas eliminadas: {total_mesclados}")
    print("=========================================================\n")
    if not silent:
        input("Pressione Enter para continuar...")

if __name__ == "__main__":
    import time
    if "--detect-only" in sys.argv:
        rodar_diagnostico_cron()
    elif "--auto-merge-exact-words" in sys.argv:
        rodar_mesclagem_automatica_exata(silent=False)
    elif "--auto-merge-exact-words-silent" in sys.argv:
        rodar_mesclagem_automatica_exata(silent=True)
    else:
        rodar_assistente_interativo()
