import sys
import os

# Adiciona a pasta raiz e a pasta functions no path para conseguir importar o Firebase Admin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import credentials, firestore

try:
    print("=========================================================")
    print("🔎 BUSCANDO ÚLTIMAS OFERTAS SALVAS NO BANCO (FIRESTORE) ")
    print("=========================================================")
    
    # Inicializa o app se ainda não estiver inicializado
    if not firebase_admin._apps:
        # Usa as credenciais padrão do ambiente local e injeta o ID do projeto
        firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
        
    db = firestore.client()
    
    # Busca as últimas 15 ofertas adicionadas
    ofertas_ref = db.collection('ofertas').order_by('criado_em', direction=firestore.Query.DESCENDING).limit(15)
    docs = ofertas_ref.stream()
    
    encontrou = False
    for doc in docs:
        encontrou = True
        d = doc.to_dict()
        loja = d.get('loja', 'Desconhecida')
        nome = d.get('produto_nome', 'Sem nome')
        preco = d.get('preco') or 0
        preco_antigo = d.get('preco_antigo') or 0
        unidade = d.get('unidade', 'un')
        categoria = d.get('categoria', 'Geral')
        criado_em = d.get('criado_em', 'Desconhecido')
        imagem = d.get('imagem', '')
        
        print(f"🏪 Loja: {loja}")
        print(f"🛒 Produto: {nome}")
        if preco_antigo > 0:
            print(f"💰 Preço: de R$ {preco_antigo} por R$ {preco} ({unidade})")
        else:
            print(f"💰 Preço: R$ {preco} ({unidade})")
        print(f"🏷️ Categoria: {categoria}")
        print(f"🕒 Salvo em: {criado_em}")
        print("-" * 50)
        
    if not encontrou:
        print("Nenhuma oferta encontrada no banco de dados ainda.")
        
except Exception as e:
    print(f"Erro ao acessar banco: {e}")
    print("\nDica: Lembre-se que para rodar scripts locais acessando o Firestore real, você precisa estar autenticado via gcloud ou ter configurado a GOOGLE_APPLICATION_CREDENTIALS.")
