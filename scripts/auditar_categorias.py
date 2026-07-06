import sys
import os
import re
import subprocess
from datetime import datetime

# Adiciona as pastas corretas ao Path para importação do Firebase Admin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore
from google import genai
from google.genai import types

def obter_api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    print("🔑 Buscando GEMINI_API_KEY do Secret Manager via gcloud...", flush=True)
    try:
        # Tenta buscar via gcloud se estiver rodando localmente sem env setado
        cmd = ["gcloud", "secrets", "versions", "access", "latest", "--secret=GEMINI_API_KEY", "--quiet"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("🔑 Chave obtida com sucesso!", flush=True)
        return res.stdout.strip()
    except Exception as e:
        print(f"⚠️ Não foi possível obter GEMINI_API_KEY do Secret Manager: {e}", flush=True)
        return None

# Inicializar Firebase
if not firebase_admin._apps:
    firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
db = firestore.client()

CATEGORIAS_VALIDAS = ["CARNES", "HORTIFRUTI", "PADARIA", "BEBIDAS", "HIGIENE", "LIMPEZA", "FRIOS_LATICINIOS", "PET"]

def obter_sugestoes_gemini(produtos):
    key = obter_api_key()
    if not key:
        print("❌ GEMINI_API_KEY não disponível. Abortando auditoria semântica.", flush=True)
        return []
    
    client = genai.Client(api_key=key)
    
    # Monta a lista compacta de produtos
    lista_texto = "\n".join([f"ID: {p['id']} | Nome: {p['nome']}" for p in produtos])
    
    prompt = f"""
    Você é um auditor de dados de supermercado de elite.
    Analise a lista de produtos abaixo (atualmente todos estão classificados como ALIMENTOS / Mercearia geral).
    
    Identifique se algum deles pertence de forma mais adequada a uma das seguintes categorias específicas:
    - CARNES (Açougue, peixaria, frangos, embutidos)
    - HORTIFRUTI (Frutas, verduras, legumes, ovos frescos)
    - BEBIDAS (Refrigerantes, sucos, águas, energéticos - não alcoólicos)
    - PADARIA (Pães, bolos, tortas, salgados de lanchonete, pratos prontos de rotisseria)
    - HIGIENE (Shampoo, sabonetes, desodorantes, fraldas, etc.)
    - LIMPEZA (Detergente, sabão em pó, desinfetantes, amaciantes, etc.)
    - FRIOS_LATICINIOS (Leite, queijos, presunto, mortadela, iogurtes, requeijão, manteiga, margarina, etc.)
    - PET (Rações, sachês úmidos pet, petiscos pet, tapetes higiênicos, coleiras, shampoos e sabonetes pet, etc.)
    
    AÇÃO DE EXCLUSÃO (Muito Importante):
    - Se um produto NÃO for um item de supermercado core (como móveis/bazar, mesa/cadeiras, eletrônicos, TVs, eletrodomésticos pesados, roupas/vestuário, brinquedos, ou bebidas alcoólicas que vazaram no scanner), sugira a palavra especial EXCLUIR para a categoria sugerida.
    
    REGRAS SEMÂNTICAS OBRIGATÓRIAS:
    - Doces, biscoitos, achocolatados, chocolates e sobremesas DEVEM permanecer em ALIMENTOS. NÃO sugira BEBIDAS, CARNES ou qualquer outra categoria para eles. Se analisar um chocolate, ignore-o (não o coloque na lista de sugestões).
    - Não sugira NENHUMA categoria fora da lista acima + a palavra EXCLUIR. Não invente categorias como "OUTROS", "MÓVEIS", "BAZAR", etc.
    
    Produtos a analisar:
    {lista_texto}

    Regras de Retorno:
    - Retorne APENAS um JSON no seguinte formato:
    {
        "sugestoes": [
            {
                "id": "ID_DO_PRODUTO",
                "nome": "NOME_DO_PRODUTO",
                "categoria_sugerida": "CATEGORIA_SUGERIDA_OU_EXCLUIR",
                "justificativa": "Breve justificativa"
            }
        ]
    }
    - Se todos os produtos estiverem classificados corretamente em ALIMENTOS, retorne "sugestoes" como uma lista vazia.
    - Não inclua comentários, Markdown ou tags no retorno, apenas o JSON puro.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
        import json
        resultado = json.loads(texto_limpo)
        return resultado.get("sugestoes", [])
    except Exception as e:
        print(f"⚠️ Erro ao chamar o Gemini: {e}", flush=True)
        return []

def auditar_categorias(detect_only=False, auto_apply=False):
    print("=========================================================", flush=True)
    print("🧹 ASSISTENTE DE AUDITORIA DE CATEGORIAS (PENTE FINO)", flush=True)
    print("=========================================================\n", flush=True)
    
    # 1. Carrega produtos classificados como ALIMENTOS
    print("⏳ Carregando produtos sob a categoria ALIMENTOS...", flush=True)
    produtos_ref = db.collection("produtos").where("categoria", "==", "ALIMENTOS").stream()
    produtos = []
    for doc in produtos_ref:
        if doc.id.startswith("_"):
            continue
        d = doc.to_dict()
        produtos.append({
            "id": doc.id,
            "nome": d.get("nome", ""),
            "categoria": d.get("categoria", "ALIMENTOS")
        })
        
    print(f"✅ {len(produtos)} produtos em ALIMENTOS carregados.", flush=True)
    if not produtos:
        print("✨ O catálogo está limpo! Nenhum produto na categoria ALIMENTOS para analisar.", flush=True)
        return
        
    # Para não estourar o limite de tokens, processamos em lotes de 100
    lote_tamanho = 100
    sugestoes_totais = []
    
    print(f"🧠 Enviando produtos para auditoria semântica da IA (Lotes de {lote_tamanho})...", flush=True)
    for i in range(0, len(produtos), lote_tamanho):
        lote = produtos[i:i+lote_tamanho]
        print(f"  📤 Analisando lote {i//lote_tamanho + 1}...", flush=True)
        sugestoes = obter_sugestoes_gemini(lote)
        sugestoes_totais.extend(sugestoes)
        time.sleep(1) # Intervalo preventivo de taxa
        
    # 1.1 Filtragem rígida de segurança antes de processar
    sugestoes_filtradas = []
    for sug in sugestoes_totais:
        prod_id = sug.get("id")
        nome = sug.get("nome", "")
        cat_sugerida = sug.get("categoria_sugerida", "").strip().upper()
        
        # Whitelist de categorias válidas + termo especial EXCLUIR
        if cat_sugerida not in CATEGORIAS_VALIDAS and cat_sugerida != "EXCLUIR":
            continue
            
        # Impede que doces e bombons sejam reclassificados incorretamente para Bebidas ou Carnes
        nome_lower = nome.lower()
        if any(x in nome_lower for x in ["bombom", "chocolate", "biscoito", "wafer", "doce", "achocolatado"]):
            if cat_sugerida in ["BEBIDAS", "CARNES"]:
                continue
                
        sugestoes_filtradas.append(sug)
        
    sugestoes_totais = sugestoes_filtradas
        
    print(f"\n🎯 A IA identificou {len(sugestoes_totais)} suspeitas válidas de categorias incorretas/exclusões.", flush=True)
    
    if not sugestoes_totais:
        print("✨ Nenhuma suspeita de classificação incorreta encontrada!", flush=True)
        return
        
    if detect_only:
        print("\n--- 📋 RELATÓRIO SILENCIOSO DE AUDITORIA ---", flush=True)
        for sug in sugestoes_totais:
            print(f"  ⚠️ [SUSPEITA] {sug.get('id')} | '{sug.get('nome')[:40]}' -> Mudar para {sug.get('categoria_sugerida')} (Motivo: {sug.get('justificativa')})", flush=True)
        print("\nFim do relatório de auditoria.", flush=True)
        return
        
    if auto_apply:
        print("\n--- 🤖 APLICAÇÃO AUTOMÁTICA DE SUGESTÕES (AUTO-APPLY) ---", flush=True)
        total_reclassificados = 0
        for idx, sug in enumerate(sugestoes_totais):
            prod_id = sug.get("id")
            nome = sug.get("nome")
            cat_sugerida = sug.get("categoria_sugerida").strip().upper()
            justificativa = sug.get("justificativa")
            
            # Recarrega o produto para garantir estado atual
            doc_prod = db.collection("produtos").document(prod_id).get()
            if not doc_prod.exists:
                continue
                
            if cat_sugerida == "EXCLUIR":
                print(f"🤖 [{idx+1}/{len(sugestoes_totais)}] [AUTO-DELETE] Removendo {prod_id} do banco (Bazar/Alcoólico)...", flush=True)
                print(f"   * Nome: {nome}")
                print(f"   * Justificativa: {justificativa}")
                
                # Deleta produto
                db.collection("produtos").document(prod_id).delete()
                # Deleta ofertas ativas
                ofertas_ref = db.collection("ofertas").where("produto_id", "==", prod_id).stream()
                of_count = 0
                for of_doc in ofertas_ref:
                    of_doc.reference.delete()
                    of_count += 1
                print(f"   ✅ Removido com sucesso! ({of_count} ofertas deletadas).", flush=True)
            else:
                print(f"🤖 [{idx+1}/{len(sugestoes_totais)}] [AUTO-UPDATE] Atualizando {prod_id} para {cat_sugerida}...", flush=True)
                print(f"   * Nome: {nome}")
                print(f"   * Justificativa: {justificativa}")
                
                # Atualiza produto
                db.collection("produtos").document(prod_id).update({"categoria": cat_sugerida})
                # Atualiza ofertas ativas
                ofertas_ref = db.collection("ofertas").where("produto_id", "==", prod_id).stream()
                of_count = 0
                for of_doc in ofertas_ref:
                    of_doc.reference.update({"categoria": cat_sugerida})
                    of_count += 1
                print(f"   ✅ Atualizado! ({of_count} ofertas vinculadas).", flush=True)
                
            total_reclassificados += 1
            time.sleep(0.3)
            
        print(f"\n🏁 Auditoria automática concluída. Total de produtos reclassificados: {total_reclassificados}", flush=True)
        return
        
    # Modo Interativo
    print("\n--- 🛠️  MODO INTERATIVO DE CORREÇÃO ---")
    print("Pressione Enter para iniciar a revisão das suspeitas...")
    input()
    
    total_reclassificados = 0
    
    for idx, sug in enumerate(sugestoes_totais):
        prod_id = sug.get("id")
        nome = sug.get("nome")
        cat_sugerida = sug.get("categoria_sugerida").strip().upper()
        justificativa = sug.get("justificativa")
        
        # Recarrega o produto para garantir estado atual
        doc_prod = db.collection("produtos").document(prod_id).get()
        if not doc_prod.exists:
            continue
            
        is_delete = (cat_sugerida == "EXCLUIR")
            
        os.system("clear")
        print(f"Revisando suspeita [{idx+1}/{len(sugestoes_totais)}]:")
        print(f"---------------------------------------------------------")
        print(f"👉 Produto:    {nome}")
        print(f"🆔 ID:         {prod_id}")
        print(f"📦 Atual:      ALIMENTOS")
        if is_delete:
            print(f"💡 Sugerida:   \033[91m{cat_sugerida} (EXCLUIR PRODUTO DO BANCO)\033[0m")
        else:
            print(f"💡 Sugerida:   \033[92m{cat_sugerida}\033[0m")
        print(f"📝 Justificativa: {justificativa}")
        print(f"---------------------------------------------------------")
        print("Escolha uma opção:")
        if is_delete:
            print("  [1] \033[91mConfirmar Exclusão (Deletar produto e ofertas do banco)\033[0m")
        else:
            print(f"  [1] \033[92mAceitar sugestão (Mover para {cat_sugerida})\033[0m")
        print("  [2] Rejeitar sugestão (Manter em ALIMENTOS)")
        print("  [3] Definir categoria manualmente")
        print("  [0] Parar auditoria e sair")
        
        opcao = input("\n👉 Opção desejada: ").strip()
        
        if opcao == "0":
            break
        elif opcao == "1":
            if is_delete:
                print(f"⏳ Deletando produto {prod_id} e suas ofertas...")
                db.collection("produtos").document(prod_id).delete()
                ofertas_ref = db.collection("ofertas").where("produto_id", "==", prod_id).stream()
                of_count = 0
                for of_doc in ofertas_ref:
                    of_doc.reference.delete()
                    of_count += 1
                print(f"✅ Deletado com sucesso! ({of_count} ofertas removidas).")
            else:
                print(f"⏳ Atualizando {prod_id} para {cat_sugerida}...")
                db.collection("produtos").document(prod_id).update({"categoria": cat_sugerida})
                ofertas_ref = db.collection("ofertas").where("produto_id", "==", prod_id).stream()
                of_count = 0
                for of_doc in ofertas_ref:
                    of_doc.reference.update({"categoria": cat_sugerida})
                    of_count += 1
                print(f"✅ Atualizado! ({of_count} ofertas vinculadas atualizadas).")
            total_reclassificados += 1
            time.sleep(1)
        elif opcao == "2":
            print("⏭️ Sugestão ignorada. Produto mantido em ALIMENTOS.")
            time.sleep(1)
        elif opcao == "3":
            print("\nCategorias disponíveis: ALIMENTOS, CARNES, HORTIFRUTI, PADARIA, BEBIDAS, HIGIENE, LIMPEZA, FRIOS_LATICINIOS, PET")
            nova_cat = input("👉 Digite a nova categoria: ").strip().upper()
            if nova_cat in ["ALIMENTOS", "CARNES", "HORTIFRUTI", "PADARIA", "BEBIDAS", "HIGIENE", "LIMPEZA", "FRIOS_LATICINIOS", "PET"]:
                print(f"⏳ Atualizando {prod_id} para {nova_cat}...")
                db.collection("produtos").document(prod_id).update({"categoria": nova_cat})
                ofertas_ref = db.collection("ofertas").where("produto_id", "==", prod_id).stream()
                for of_doc in ofertas_ref:
                    of_doc.reference.update({"categoria": nova_cat})
                print("✅ Atualizado com sucesso!")
                total_reclassificados += 1
            else:
                print("❌ Categoria inválida! Operação cancelada.")
            time.sleep(1.5)
            
    print(f"\n🏁 Auditoria concluída. Total de produtos reclassificados/removidos: {total_reclassificados}")

if __name__ == "__main__":
    import time
    detect = "--detect-only" in sys.argv
    auto = "--auto-apply" in sys.argv
    try:
        auditar_categorias(detect_only=detect, auto_apply=auto)
    except KeyboardInterrupt:
        print("\n\n👋 Auditoria interrompida pelo usuário.")
        sys.exit(0)
