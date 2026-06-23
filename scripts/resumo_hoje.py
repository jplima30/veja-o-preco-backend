import sys
import os
from datetime import datetime, timezone, timedelta

# Adiciona a pasta functions no path para conseguir importar o Firebase Admin
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

def gerar_resumo():
    print("\n" + "="*70)
    print("📊 RELATÓRIO DIÁRIO DE OFERTAS E IMAGENS COLETADAS HOJE (NUVEM & LOCAL)")
    print("="*70)
    
    # Inicializa o app se ainda não estiver inicializado
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
        
    db = firestore.client()
    
    # Define o início do dia de hoje no fuso horário UTC (Firestore armazena em UTC)
    agora_utc = datetime.now(timezone.utc)
    hoje_inicio_utc = agora_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Para o fuso do Brasil (UTC-3), podemos ajustar para pegar desde 03:00 UTC do dia atual 
    # para cobrir o dia a partir de 00:00 local.
    hoje_inicio_br = hoje_inicio_utc + timedelta(hours=3)
    
    ofertas_ref = db.collection('ofertas')
    query = ofertas_ref.where(filter=FieldFilter('criado_em', '>=', hoje_inicio_br)).order_by('criado_em', direction=firestore.Query.ASCENDING)
    docs = query.stream()
    
    ofertas_por_loja = {}
    total_ofertas = 0
    com_storage = 0
    com_externo = 0
    sem_imagem = 0
    
    for doc in docs:
        d = doc.to_dict()
        loja = d.get('loja', 'Outros')
        prod = d.get('produto_nome', 'Sem nome')
        preco = d.get('preco', 0)
        unidade = d.get('unidade', 'un')
        img_url = d.get('imagem_url', '')
        criado_em = d.get('criado_em')
        
        # Converte criado_em para exibição local (UTC-3)
        if criado_em:
            criado_local = criado_em.astimezone(timezone(timedelta(hours=-3)))
            hora_str = criado_local.strftime("%H:%M")
        else:
            hora_str = "--:--"
            
        status_img = "❌ SEM IMAGEM"
        if img_url:
            if any(host in img_url for host in ["firebasestorage.googleapis.com", "storage.googleapis.com"]):
                status_img = "✅ STORAGE"
                com_storage += 1
            else:
                status_img = "⚠️ LINK EXTERNO"
                com_externo += 1
        else:
            sem_imagem += 1
            
        total_ofertas += 1
        
        if loja not in ofertas_por_loja:
            ofertas_por_loja[loja] = []
        ofertas_por_loja[loja].append({
            "produto": prod,
            "preco": preco,
            "unidade": unidade,
            "status_img": status_img,
            "hora": hora_str
        })
        
    if total_ofertas == 0:
        print("\n📭 Nenhuma oferta nova foi encontrada no banco de dados hoje até o momento.")
        print("  Dica: Verifique se o CRON da nuvem ou a triagem local já finalizaram com sucesso.")
        print("="*70 + "\n")
        return
        
    # Exibe resumo detalhado por loja
    for loja, itens in ofertas_por_loja.items():
        print(f"\n🏪 Supermercado: {loja} ({len(itens)} ofertas)")
        print("-" * 70)
        # Formata colunas de ofertas
        print(f"{'HORA':<6} | {'PRODUTO':<38} | {'PREÇO':<10} | {'IMAGEM':<12}")
        print("-" * 70)
        for it in itens:
            prod_trunc = it["produto"][:36] + "..." if len(it["produto"]) > 38 else it["produto"]
            preco_str = f"R$ {it['preco']:.2f} ({it['unidade']})"
            print(f"{it['hora']:<6} | {prod_trunc:<38} | {preco_str:<10} | {it['status_img']:<12}")
            
    # Estatísticas Finais
    print("\n" + "="*70)
    print("📊 ESTATÍSTICAS DO DIA")
    print("="*70)
    print(f"📈 Total de Ofertas Processadas Hoje: {total_ofertas}")
    print(f"  - Imagens convertidas para o Storage: {com_storage} ({(com_storage/total_ofertas*100):.1f}%)")
    print(f"  - Mantidas com links externos:        {com_externo} ({(com_externo/total_ofertas*100):.1f}%)")
    print(f"  - Ofertas sem imagem de produto:      {sem_imagem} ({(sem_imagem/total_ofertas*100):.1f}%)")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        gerar_resumo()
    except Exception as e:
        print(f"❌ Erro ao gerar relatório diário: {e}")
