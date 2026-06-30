import sys
import os
import requests
import io
import urllib.parse
from PIL import Image, ImageOps

# Adiciona as pastas corretas ao Path para importação do Firebase Admin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore, storage

def inicializar_firebase():
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
    return firestore.client(), storage.bucket("veja-o-preco.firebasestorage.app")

def buscar_open_food_facts(nome_produto: str) -> str:
    """
    Busca a imagem do produto no Open Food Facts usando o nome.
    """
    try:
        query_safe = urllib.parse.quote(nome_produto)
        url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query_safe}&search_simple=1&action=process&json=1&page_size=1"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            dados = resp.json()
            produtos = dados.get("products", [])
            if produtos:
                imagem = produtos[0].get("image_front_url", "")
                if imagem:
                    return imagem
    except Exception as e:
        print(f"  ⚠️ Erro na busca do Open Food Facts: {e}")
    return ""

def processar_e_otimizar_imagem(url_imagem: str) -> io.BytesIO:
    """
    Baixa uma imagem da internet, ajusta sua proporção com preenchimento branco (200x200) e comprime para JPEG 75%.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url_imagem, headers=headers, timeout=10)
    resp.raise_for_status()
    
    img_bytes = io.BytesIO(resp.content)
    with Image.open(img_bytes) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Redimensionamento 200x200 preservando proporção
        img_redimensionada = ImageOps.pad(img, (200, 200), color="white", centering=(0.5, 0.5))
        
        output = io.BytesIO()
        img_redimensionada.save(output, "JPEG", quality=75)
        output.seek(0)
        return output

def curar_imagens():
    print("=========================================================")
    print("🧹 INICIANDO HIGIENIZAÇÃO E CURAÇÃO DE IMAGENS DE PRODUTOS")
    print("=========================================================\n")
    
    db, bucket = inicializar_firebase()
    
    # 1. Obter todos os produtos do Firestore
    print("⏳ Carregando produtos do Firestore...")
    produtos_ref = db.collection("produtos")
    docs = list(produtos_ref.stream())
    print(f"✅ {len(docs)} produtos carregados.\n")
    
    # 2. Filtrar produtos que precisam de imagem ou que têm recorte de IA
    produtos_pendentes = []
    for doc in docs:
        d = doc.to_dict()
        url = d.get("imagem_url", "")
        origem = d.get("imagem_origem", "")
        
        # Pendente se: URL vazia, sem origem registrada, origem 'padrao' ou 'auto_crop' (recorte de IA)
        if not url or origem == "auto_crop" or origem == "padrao" or not origem:
            produtos_pendentes.append((doc.id, d))
            
    if not produtos_pendentes:
        print("🎉 Nenhuma imagem pendente de higienização ou atualização!")
        print("Todos os produtos possuem imagens curadas de alta qualidade.\n")
        return
        
    print(f"📂 Encontrados {len(produtos_pendentes)} produtos pendentes de curação.")
    print("---------------------------------------------------------")
    
    total_atualizados = 0
    
    for i, (prod_id, prod_data) in enumerate(produtos_pendentes):
        nome = prod_data.get("nome", "Sem nome")
        unidade = prod_data.get("unidade", "un")
        origem_atual = prod_data.get("imagem_origem", "desconhecida")
        
        print(f"\n📦 [{i+1}/{len(produtos_pendentes)}] Produto: {nome} ({unidade})")
        print(f"   ID: {prod_id}")
        print(f"   Status Atual: {origem_atual.upper()}")
        
        url_selecionada = ""
        origem_selecionada = ""
        
        # Passo 1: Busca automática no Open Food Facts
        print("   🔍 Buscando automaticamente no Open Food Facts...")
        url_off = buscar_open_food_facts(nome)
        
        if url_off:
            print(f"   🤖 Achou no Open Food Facts: {url_off}")
            opcao = input("   👉 Usar essa imagem? [Y] Sim / [N] Não (Buscar manual) / [S] Pular produto: ").strip().lower()
            if opcao == "" or opcao == "y" or opcao == "yes":
                url_selecionada = url_off
                origem_selecionada = "open_food_facts"
            elif opcao == "s" or opcao == "skip":
                print("   ⏭️ Produto pulado.")
                continue
        else:
            print("   ❌ Não encontrado no Open Food Facts.")
            
        # Passo 2: Entrada manual caso não tenha selecionado a automática
        if not url_selecionada:
            opcao_manual = input("   🔗 Cole a URL da imagem da internet (ou aperte Enter para PULAR): ").strip()
            if not opcao_manual:
                print("   ⏭️ Produto pulado.")
                continue
            url_selecionada = opcao_manual
            origem_selecionada = "manual"
            
        # Passo 3: Baixar, Processar e Fazer Upload
        try:
            print("   ⏳ Baixando e otimizando imagem...")
            buffer_otimizado = processar_e_otimizar_imagem(url_selecionada)
            
            print("   ☁️ Fazendo upload para o Firebase Storage...")
            blob_name = f"produtos/{prod_id}.jpg"
            blob = bucket.blob(blob_name)
            blob.upload_from_string(buffer_otimizado.getvalue(), content_type="image/jpeg")
            blob.make_public()
            public_url = blob.public_url
            
            print("   💾 Salvando metadados no Firestore...")
            ref_doc = produtos_ref.document(prod_id)
            ref_doc.update({
                "imagem_url": public_url,
                "imagem_origem": origem_selecionada,
                "atualizado_em": datetime.now()
            })
            
            tamanho_kb = len(buffer_otimizado.getvalue()) / 1024.0
            print(f"   ✅ SUCESSO! Imagem curada salva com sucesso ({tamanho_kb:.2f} KB)!")
            total_atualizados += 1
            
        except Exception as e_proc:
            print(f"   ❌ ERRO ao processar e salvar imagem: {e_proc}")
            
    print("\n=========================================================")
    print("🏁 HIGIENIZAÇÃO DE IMAGENS CONCLUÍDA!")
    print(f"📈 Total de produtos atualizados com imagem curada: {total_atualizados}")
    print("=========================================================\n")

if __name__ == "__main__":
    try:
        curar_imagens()
    except KeyboardInterrupt:
        print("\n\n👋 Operação cancelada pelo usuário.")
        sys.exit(0)
