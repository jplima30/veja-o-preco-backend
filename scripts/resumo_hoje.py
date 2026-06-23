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
    
    ofertas_site = {}
    ofertas_social = {}
    total_site = 0
    com_storage_site = 0
    com_externo_site = 0
    sem_imagem_site = 0
    total_social = 0
    
    for doc in docs:
        d = doc.to_dict()
        loja = d.get('loja', 'Outros')
        prod = d.get('produto_nome', 'Sem nome')
        preco = d.get('preco', 0)
        unidade = d.get('unidade', 'un')
        img_url = d.get('imagem_url', '')
        criado_em = d.get('criado_em')
        metodo = d.get('metodo', '')
        
        # Converte criado_em para exibição local (UTC-3)
        if criado_em:
            criado_local = criado_em.astimezone(timezone(timedelta(hours=-3)))
            hora_str = criado_local.strftime("%H:%M")
        else:
            hora_str = "--:--"
            
        es_rede_social = (metodo == 'gemini_vision')
        
        if es_rede_social:
            if loja == "Extração via Visão (IA)":
                supermercado_id = d.get('supermercado_id', '')
                if supermercado_id:
                    loja = f"Insta/Face ({supermercado_id})"
            
            total_social += 1
            if loja not in ofertas_social:
                ofertas_social[loja] = []
            ofertas_social[loja].append({
                "produto": prod,
                "preco": preco,
                "unidade": unidade,
                "hora": hora_str
            })
        else:
            status_img = "❌ SEM IMAGEM"
            if img_url:
                if any(host in img_url for host in ["firebasestorage.googleapis.com", "storage.googleapis.com"]):
                    status_img = "✅ STORAGE"
                    com_storage_site += 1
                else:
                    status_img = "⚠️ LINK EXTERNO"
                    com_externo_site += 1
            else:
                sem_imagem_site += 1
                
            total_site += 1
            if loja not in ofertas_site:
                ofertas_site[loja] = []
            ofertas_site[loja].append({
                "produto": prod,
                "preco": preco,
                "unidade": unidade,
                "status_img": status_img,
                "hora": hora_str
            })
        
    if total_site == 0 and total_social == 0:
        print("\n📭 Nenhuma oferta nova foi encontrada no banco de dados hoje até o momento.")
        print("  Dica: Verifique se o CRON da nuvem ou a triagem local já finalizaram com sucesso.")
        print("="*70 + "\n")
        return
        
    # 1. Seção de Sites/E-commerce
    if total_site > 0:
        print("\n" + "="*70)
        print("🛍️  CONVERSÃO DE IMAGENS DE SITES / E-COMMERCE (200x200)")
        print("="*70)
        for loja, itens in ofertas_site.items():
            print(f"\n🏪 Supermercado: {loja} ({len(itens)} ofertas)")
            print("-" * 70)
            print(f"{'HORA':<6} | {'PRODUTO':<38} | {'PREÇO':<10} | {'IMAGEM':<12}")
            print("-" * 70)
            for it in itens:
                prod_trunc = it["produto"][:36] + "..." if len(it["produto"]) > 38 else it["produto"]
                preco_str = f"R$ {it['preco']:.2f} ({it['unidade']})"
                print(f"{it['hora']:<6} | {prod_trunc:<38} | {preco_str:<10} | {it['status_img']:<12}")

    # 2. Seção de Redes Sociais
    if total_social > 0:
        print("\n" + "="*70)
        print("📱 EXTRAÇÕES DE REDES SOCIAIS (Triagem OCR Local + Visão Gemini)")
        print("  * Nota: Estas ofertas não possuem fotos individuais de produto.")
        print("="*70)
        for loja, itens in ofertas_social.items():
            print(f"\n🏪 Canal: {loja} ({len(itens)} ofertas)")
            print("-" * 70)
            print(f"{'HORA':<6} | {'PRODUTO':<38} | {'PREÇO':<10} | {'IMAGEM':<12}")
            print("-" * 70)
            for it in itens:
                prod_trunc = it["produto"][:36] + "..." if len(it["produto"]) > 38 else it["produto"]
                preco_str = f"R$ {it['preco']:.2f} ({it['unidade']})"
                print(f"{it['hora']:<6} | {prod_trunc:<38} | {preco_str:<10} | {'🎨 ÍCONE APP':<12}")
            
    # Estatísticas Finais
    print("\n" + "="*70)
    print("📊 ESTATÍSTICAS DA OPERAÇÃO DE HOJE")
    print("="*70)
    print(f"📈 Total de Ofertas Processadas Hoje: {total_site + total_social}")
    
    if total_site > 0:
        print(f"\n💻 Sites & E-commerce ({total_site} itens):")
        print(f"  - Imagens convertidas para o Storage: {com_storage_site} ({(com_storage_site/total_site*100):.1f}%)")
        print(f"  - Mantidas com links externos:        {com_externo_site} ({(com_externo_site/total_site*100):.1f}%)")
        print(f"  - Sem imagem de produto:              {sem_imagem_site} ({(sem_imagem_site/total_site*100):.1f}%)")
        
    if total_social > 0:
        print(f"\n📱 Redes Sociais ({total_social} itens):")
        print(f"  - Usando ícones de categoria (padrão): {total_social} (100.0%)")
        
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        gerar_resumo()
    except Exception as e:
        print(f"❌ Erro ao gerar relatório diário: {e}")
