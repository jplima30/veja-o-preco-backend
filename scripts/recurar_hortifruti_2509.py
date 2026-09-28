#!/usr/bin/env python3
"""
RE-CURAÇÃO HORTIFRUTI 25/09 — ETAPA 2 (aplicação).
As 9 URLs abaixo foram PESQUISADAS e ESCOLHIDAS visualmente pelo agente
(Bing Images navegação manual + verificação em galeria, 9/9 carregando).
Aplica o PADRÃO OFICIAL do projeto a cada escolha:
  download -> 400x400 fundo branco #FFFFFF (JPEG Q80) -> Storage
  -> /produtos (imagem_url, origem=estudio_400x400, imagem_fonte_pesquisa)
  -> propaga /ofertas.

Uso: functions/venv/bin/python3 scripts/recurar_hortifruti_2509.py
"""

import io
import os
import sys
import time
import requests
from datetime import datetime
from PIL import Image, ImageOps

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../functions")))

import firebase_admin
from firebase_admin import credentials, firestore, storage

# (produto_id, url escolhida visualmente, fonte citada)
ESCOLHAS = [
    ("laranja-sitio-famosa-un",
     "https://www.newcitrus.com.br/wp-content/uploads/2015/12/laranja-pera-rio-embalada-2-scaled.jpg",
     "New Citrus (produtor, laranja pêra embalada)"),
    ("maracuja-kg",
     "https://3.bp.blogspot.com/-b6zadRiJe6I/WMhJJoLLNVI/AAAAAAAACYo/UGJoHqSybyUgFW_YfNyuUgwtp2DzVrd6wCLcB/s1600/Maracuja%2BAzedo%2BRoxo%2Bpassiflora%2Bedulis.jpg",
     "Viveiro Ciprest (maracujá azedo roxo, Passiflora edulis)"),
    ("melao-amarelo-famosa-kg",
     "https://www.sondadelivery.com.br/img.aspx/sku/46186/530/NovoProjeto-2022-02-18T081614-754.jpg",
     "Sonda (packshot Melão Amarelo Famosa 1,6kg, marca exata)"),
    ("morangos-congelados-de-marchi-un",
     "https://www.sondadelivery.com.br/Arquivos/ProdutosSku/1000047854/7896519251674.png",
     "Sonda (packshot Morango Congelado De Marchi pouch)"),
    ("uva-vermelha-cappellaro-un",
     "https://covabra.vtexassets.com/arquivos/ids/535581/107320.jpg?v=638925296898900000",
     "Covabra VTEX (Uva Vermelha Cappellaro Fruits 500g)"),
    ("cebola-roxa-kg",
     "https://www.biocabaz.pt/web/wp-conteudos/uploads/2016/03/cebola-roxa.jpg",
     "Biocabaz (cebolas roxas, foto limpa)"),
    ("batata-lavada-kg",
     "https://phygital-files.mercafacil.com/lisboa-bucket/uploads/produto/legumes_batata_lavada_kg_97751e43-ed2b-4d48-b316-bbe7b62ee140.jpeg",
     "Supermercado Lisboa / Mercafacil (Batata Lavada KG)"),
    ("maca-nacional-kg",
     "https://comper.vteximg.com.br/arquivos/ids/181051-1000-1000/631582.jpg?v=637436416807170000",
     "Comper VTEX (Maçã Nacional KG)"),
    ("uva-vitoria-grandvalle-un",
     "https://grandvalle.com.br/wp-content/uploads/2023/12/packuva-1-1-1.png",
     "Site oficial Grand Valle (pack uva Vitória)"),
]

BA = "https://storage.googleapis.com/veja-o-preco.firebasestorage.app"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def processar_400x400(conteudo: bytes) -> bytes:
    """Padrão oficial do projeto: 400x400, encaixe proporcional, fundo branco #FFFFFF, JPEG Q80."""
    img = Image.open(io.BytesIO(conteudo))
    if img.mode != "RGB":
        img = img.convert("RGB")
    fundo = Image.new("RGB", (400, 400), (255, 255, 255))
    img = ImageOps.contain(img, (400, 400))
    fundo.paste(img, ((400 - img.width) // 2, (400 - img.height) // 2))
    buf = io.BytesIO()
    fundo.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()


def main():
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.ApplicationDefault(), options={"projectId": "veja-o-preco"})
    db = firestore.client()
    bucket = storage.bucket("veja-o-preco.firebasestorage.app")
    ok, falhas = [], []

    for pid, url, fonte in ESCOLHAS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            r.raise_for_status()
            jpg = processar_400x400(r.content)

            blob = bucket.blob(f"produtos/{pid}.jpg")
            blob.upload_from_string(jpg, content_type="image/jpeg")
            blob.make_public()
            nova_url = f"{BA}/produtos/{pid}.jpg?t={int(time.time())}"

            db.collection("produtos").document(pid).set({
                "imagem_url": nova_url,
                "imagem_origem": "estudio_400x400",
                "imagem_fonte_pesquisa": fonte,
                "imagem_atualizada_em": datetime.now(),
            }, merge=True)

            # propaga para /ofertas ativas deste produto
            ofertas = db.collection("ofertas").where(
                filter=firestore.FieldFilter("produto_id", "==", pid)).stream()
            n_of = 0
            for o in ofertas:
                o.reference.set({"imagem_url": nova_url}, merge=True)
                n_of += 1

            ok.append((pid, len(jpg), n_of))
            print(f"  ✅ {pid}  {len(jpg)//1024} KB  ofertas={n_of}")
        except Exception as e:
            falhas.append((pid, str(e)[:100]))
            print(f"  ❌ {pid}: {e}")

    print(f"\nConcluído: {len(ok)} aplicadas, {len(falhas)} falhas")
    if falhas:
        for pid, e in falhas:
            print(f"  FALHOU: {pid}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
