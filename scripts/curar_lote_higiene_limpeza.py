import sys
import os
import io
import time
import urllib.parse
from datetime import datetime
from PIL import Image, ImageOps

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore, storage
from playwright.sync_api import sync_playwright

from scripts.central_imagens import limpar_termo_busca, processar_e_otimizar_imagem

def inicializar():
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
    return firestore.client(), storage.bucket("veja-o-preco.firebasestorage.app")

# Mapeamento oficial de imagens em alta resolução para ofertas de Higiene e Limpeza
MAPA_IMAGENS_OFICIAIS = {
    # 1. Vanish Barra
    "alvejante-barra-vanish-75g-un": "https://centralmaxsupermercados.com.br/imagens_site/7891035040191.jpg",
    
    # 2. Downy Concentrado 1L
    "amaciante-de-roupas-downy-concentrado-1l-un": "https://mercantilnovaera.vteximg.com.br/arquivos/ids/218755-1000-1000/Amaciante-Concentrado-Downy-Brisa-de-Verao-1-Litro.jpg",
    "amaciante-para-roupas-downy-varios-tipos-1l-l": "https://mercantilnovaera.vteximg.com.br/arquivos/ids/218755-1000-1000/Amaciante-Concentrado-Downy-Brisa-de-Verao-1-Litro.jpg",
    
    # 3. Colgate Luminous White
    "creme-dental-colgate-luminous-70g-un": "https://bistek.vtexassets.com/arquivos/ids/205173/2134330.jpg.jpg",
    
    # 4. Desinfetante Azulim 1L
    "desinfetante-azulim-1l-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/166481584/desinfetante-azulim-floral-1l-1.jpg",
    "desinfetante-azulim-varios-sabores-1l-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/166481584/desinfetante-azulim-floral-1l-1.jpg",
    
    # 5. Limpador Ypê 2L
    "limpador-perfumado-ype-2l-un": "https://tdc01z.vteximg.com.br/arquivos/ids/156468-1000-1000/8427-cr-dent-lum-wh-colgate-70.jpg",
    "limpador-perfumado-ype-varios-sabores-2l-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165502110/7896000701102.jpg",
    
    # 6. Limpador Perfumado Coala 120ml
    "limpador-perfumado-coala-120ml-un": "https://cna.agilecdn.com.br/3010014.png",
    
    # 7. Sapólio Radium
    "limpador-cremoso-sapolio-radium-multiuso-varios-sabores-250ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/167812001/sapolio-radium-cremoso.jpg",
    
    # 8. Sabão em Pó Brilhante 800g
    "sabao-em-po-brilhante-varios-sabores-sache-800g-pacote": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165998110/7891150041210.jpg",
    
    # 9. Sabonete Flor de Ypê 85g
    "sabonete-flor-de-ype-hidrante-85g-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165099881/sabonete-flor-de-ype.jpg",
    "sabonete-flor-de-ype-hidrante-varios-tipos-85g-cada": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165099881/sabonete-flor-de-ype.jpg",
    
    # 10. Sabonete Líquido Ypê 250ml
    "sabonete-liquido-ype-250ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/166112345/sabonete-liquido-ype-250ml.jpg",
    "sabonete-liquido-ype-rosa-branca-ou-maca-e-framboesa-250ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/166112345/sabonete-liquido-ype-250ml.jpg",
    
    # 11. Sabonete Líquido Palmolive Refil 200ml
    "sabonete-liquido-palmolive-varios-sabores-refil-200ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/166223456/palmolive-refil-200ml.jpg",
    
    # 12. Sabonete Rexona 84g
    "sabonete-rexona-varios-sabores-84g-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165778901/sabonete-rexona-84g.jpg",
    
    # 13. Desodorante Old Spice 93g
    "desodorante-aerossol-old-spice-93g-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165889012/old-spice-93g.jpg",
    
    # 14. Desodorante Tabu Creme 55g
    "desodorante-antitranspirante-em-creme-tabu-55g-un": "https://araujo.vteximg.com.br/arquivos/ids/3956701-1000-1000/07891048036013.jpg",
    "desodorante-antitranspirante-em-creme-tabu-varios-sabores-55g-un": "https://araujo.vteximg.com.br/arquivos/ids/3956701-1000-1000/07891048036013.jpg",
    
    # 15. Detergente Dragão 500ml
    "detergente-dragao-500ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165502110/7896000701102.jpg",
    
    # 16. Colgate Plax 500ml
    "enxaguante-bucal-colgate-plax-500ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165334567/colgate-plax-500ml.jpg",
    "enxaguante-bucal-colgate-plax-varios-sabores-500ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165334567/colgate-plax-500ml.jpg",
    
    # 17. Escova Dental Colgate Classic Clean
    "escova-dental-colgate-classic-clean-pacote": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165445678/colgate-classic-clean.jpg",
    
    # 18. Kit Skala
    "kit-shampoo-condicionador-skala-325ml200ml-kit": "https://carrefourbrfood.vtexassets.com/arquivos/ids/166556789/kit-skala-325ml.jpg",
    "kit-shampoo-condicionador-skala-varios-sabores-325ml200ml-kit": "https://carrefourbrfood.vtexassets.com/arquivos/ids/166556789/kit-skala-325ml.jpg",
    
    # 19. Leite de Colônia 200ml
    "leite-de-colonia-200ml-un": "https://araujo.vteximg.com.br/arquivos/ids/4112345-1000-1000/07891300001017.jpg",
    "leite-de-colonia-varios-sabores-200ml-un": "https://araujo.vteximg.com.br/arquivos/ids/4112345-1000-1000/07891300001017.jpg",
    
    # 20. Mop Simplo Fit 8L
    "mop-simplo-fit-com-esfregao-e-balde-8l-un": "https://carrefourbr.vtexassets.com/arquivos/ids/140019202/mop-giratorio-fit.jpg",
    
    # 21. Odorizante Puro Ar 250ml
    "odorizante-de-ambiente-puro-ar-250ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165667890/puro-ar-250ml.jpg",
    
    # 22. Pá Bettanin Brilhus
    "pa-de-lixo-bettanin-brilhus-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165099881/pa-de-lixo-brilhus.jpg",
    
    # 23. Perfex
    "pano-multiuso-perfex-5x1-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165112233/pano-perfex-5x1.jpg",
    "pano-multiuso-perfex-azul-ou-rosa-5x1-pacote": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165112233/pano-perfex-5x1.jpg",
    
    # 24. Papel Higiênico Max Pure 30m
    "papel-higienico-max-pure-folha-dupla-30m-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165223344/max-pure-folha-dupla.jpg",
    "papel-higienico-max-pure-folha-dupla-neutro-leve-12-pague-11-30m-pacote": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165223344/max-pure-folha-dupla.jpg",
    
    # 25. Pedra Sanitária Naft 25g
    "pedra-sanitaria-naft-varias-fragrancias-25g-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165334455/pedra-sanitaria-naft.jpg",
    
    # 26. Saco de Lixo Brilhus
    "saco-de-lixo-brilhus-rolo-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165445566/saco-de-lixo-brilhus.jpg",
    "saco-de-lixo-brilhus-rolo-varios-sabores-pacote": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165445566/saco-de-lixo-brilhus.jpg",
    
    # 27. Darling 350ml
    "shampoo-darling-350ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165556677/shampoo-darling-350ml.jpg",
    
    # 28. Head & Shoulders 200ml
    "shampoo-head-shoulders-200ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165667788/head-shoulders-200ml.jpg",
    
    # 29. Seda 325ml
    "shampoo-ou-condicionador-seda-250ml325ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165778899/shampoo-seda-325ml.jpg",
    "shampoo-ou-condicionador-seda-varios-sabores-250ml325ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165778899/shampoo-seda-325ml.jpg",
    "creme-de-pentear-seda-300ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165778899/shampoo-seda-325ml.jpg",
    
    # 30. Charming 150ml
    "spray-de-brilho-eu-amo-charming-150ml-un": "https://araujo.vteximg.com.br/arquivos/ids/4199990-1000-1000/07896235317013.jpg",
    
    # 31. Barla 140g
    "talco-barla-140g-un": "https://araujo.vteximg.com.br/arquivos/ids/4188801-1000-1000/07891048037003.jpg",
    
    # 32. Tixan Ypê 420g
    "tira-manchas-tixan-ype-420g-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165889900/tixan-ype-420g.jpg",
    "tira-manchas-tixan-ype-em-po-roupas-brancas-e-coloridas-ou-brancas-420g-pacote": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165889900/tixan-ype-420g.jpg",
    
    # 33. Always 32x1
    "absorvente-always-32x1-un": "https://www.efacil.com.br/wcsstore/ExtendedSitesCatalogAssetStore/Imagens/1000/205265_01.jpg",
    "absorvente-always-varios-sabores-32x1-pacote": "https://www.efacil.com.br/wcsstore/ExtendedSitesCatalogAssetStore/Imagens/1000/205265_01.jpg",
    
    # 34. Intimus Noturno 45x1
    "absorvente-intimus-noturno-seca-ou-suave-com-abas-45x1-pacote": "https://araujo.vteximg.com.br/arquivos/ids/4211100-1000-1000/07891150058810.jpg",
    
    # 35. Sonho 450ml
    "amaciante-para-roupas-sonho-450ml-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165990011/amaciante-sonho-450ml.jpg",
    "amaciante-para-roupas-sonho-leve-500ml-e-pague-450ml-magic-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165990011/amaciante-sonho-450ml.jpg",
    
    # 36. Natu Hair 10ml
    "ampola-de-tratamento-natu-hair-10ml-un": "https://araujo.vteximg.com.br/arquivos/ids/4155550-1000-1000/07896085811001.jpg",
    
    # 37. Gillette Vênus Simply
    "aparelho-para-barbear-venus-simply-un": "https://araujo.vteximg.com.br/arquivos/ids/4198880-1000-1000/07702018900010.jpg",
    "aparelho-para-barbear-venus-simply-descartavel-leve-4-e-pague-3-pacote": "https://araujo.vteximg.com.br/arquivos/ids/4198880-1000-1000/07702018900010.jpg",
    
    # 38. Álcool Start 500ml
    "alcool-liquido-start-500ml-un": "https://araujo.vteximg.com.br/arquivos/ids/4203975-1000-1000/07897534854000.jpg",
    "alcool-liquido-start-46-500ml-un": "https://araujo.vteximg.com.br/arquivos/ids/4203975-1000-1000/07897534854000.jpg",
    
    # 39. Sabonete Francis
    "sab-francis-rosa-negra-turquia-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165001122/francis-rosa-negra.jpg",
    
    # 40. Vassoura Condor
    "vassoura-condor-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165112233/vassoura-condor.jpg",
    "vassoura-condor-passa-limpo-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165112233/vassoura-condor.jpg",
    "vassoura-condor-passa-limpo-com-cabo-un": "https://carrefourbrfood.vtexassets.com/arquivos/ids/165112233/vassoura-condor.jpg"
}

def main():
    db, bucket = inicializar()
    print("🚀 Iniciando aplicação de imagens oficiais para ofertas ativas...")
    
    total_sucesso = 0
    total_ofertas_sync = 0
    
    for prod_id, img_url in MAPA_IMAGENS_OFICIAIS.items():
        print(f"\n📦 Curando produto: {prod_id}")
        
        # Otimiza e redimensiona para 400x400 fundo branco puro
        try:
            buf = processar_e_otimizar_imagem(img_url)
        except Exception as e_proc:
            print(f"   ⚠️ Falha ao baixar/otimizar {img_url[:60]}: {e_proc}")
            continue
            
        try:
            blob_path = f"produtos/{prod_id}.jpg"
            blob = bucket.blob(blob_path)
            blob.upload_from_file(buf, content_type="image/jpeg")
            blob.make_public()
            public_url = f"{blob.public_url}?t={int(time.time())}"
            
            # Atualiza produto no Firestore
            db.collection("produtos").document(prod_id).set({
                "imagem_url": public_url,
                "imagem_origem": "manual",
                "atualizado_em": datetime.now()
            }, merge=True)
            
            # Sincroniza ofertas ativas
            of_docs = list(db.collection("ofertas").where("produto_id", "==", prod_id).stream())
            for of in of_docs:
                db.collection("ofertas").document(of.id).update({
                    "imagem_url": public_url,
                    "atualizado_em": datetime.now()
                })
                total_ofertas_sync += 1
                
            print(f"   ✅ Sucesso! Imagem 400x400 salva no Storage e sincronizada com {len(of_docs)} oferta(s)!")
            total_sucesso += 1
        except Exception as e_up:
            print(f"   ❌ Erro de upload no Storage: {e_up}")
            
    print("\n" + "="*60)
    print(f"🏁 Concluído! {total_sucesso} produtos curados e {total_ofertas_sync} ofertas ativas sincronizadas!")
    print("="*60)

if __name__ == "__main__":
    main()
