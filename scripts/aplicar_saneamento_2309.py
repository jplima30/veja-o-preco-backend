#!/usr/bin/env python3
"""
SANEAMENTO 23/09 — ETAPA 2 (aplicação).
As URLs abaixo foram PESQUISADAS e ESCOLHIDAS visualmente pelo agente
(Bing Images navegação manual + verificação em galeria, 14/14 carregando).
Este script apenas aplica o PADRÃO OFICIAL do projeto a cada escolha:
  download -> 400x400 fundo branco #FFFFFF (JPEG Q80) -> Storage
  -> /produtos (imagem_url, origem=estudio_400x400) -> propaga /ofertas.

Uso: functions/venv/bin/python3 scripts/aplicar_saneamento_2309.py
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
from firebase_admin import firestore, storage

# (produto_id, url escolhida visualmente, origem citada no laudo)
ESCOLHAS = [
    ("rap-10-integral-pullman-330g-un",
     "https://img.megaboxatacado.com.br/produto/1000X1000/20151023_rap%2010%20verde.jpg",
     "Mega Box Atacado (packshot oficial wrap integral 330g)"),
    ("azeite-extra-virgem-grego-mykonos-500ml-un",
     "https://www.sondadelivery.com.br/img.aspx/sku/1240099/530/9001a48d-d66c-4229-a8c1-1a338991cffc.jpg",
     "Sonda Supermercado (varejo, packshot Mykonos 500ml)"),
    ("torrada-marilan-magic-toast-inegral-110g-un",
     "https://www.grupomarilan.com.br/images/produtos/0634824001748026154.webp",
     "Site oficial Grupo Marilan (fabricante, Magic Toast Integral 110g)"),
    ("canela-em-po-br-spices-50g-un",
     "https://carrefourbrfood.vtexassets.com/arquivos/ids/108255170/canela-em-po-br-spices-vd-50g-1.jpg?v=638158793145600000",
     "Carrefour VTEX (pote dosador BR Spices 50g)"),
    ("tempero-para-hamburguer-heinz-80g-un",
     "https://carrefourbrfood.vtexassets.com/arquivos/ids/185908819/tempero-moed-hamburguer-br-spices-80g-3.jpg?v=638761876079730000",
     "Carrefour VTEX (moedor BR Spices/Heinz 80g)"),
    ("creme-dental-tandy-uvaventura-50g-un",
     "https://muffatosupermercados.vtexassets.com/arquivos/ids/425399-800-auto?v=639034957297500000&width=800&height=auto&aspect=true",
     "Muffato VTEX (packshot Colgate Tandy Uva Ventura 50g)"),
    ("cappuccino-santa-clara-classic-gf-26o-ml-un",
     "https://www.cafesantaclara.com.br/wp-content/uploads/2022/06/iced-cappuccino-classic.png",
     "Site oficial Café Santa Clara (Iced Cappuccino Classic 260ml)"),
    ("melao-pele-de-sapo-kg",
     "https://carrefourbrfood.vtexassets.com/arquivos/ids/14648751/melao-pele-de-sapo-3-kg-1.jpg?v=637511892756400000",
     "Carrefour VTEX (melão pele de sapo inteiro)"),
    ("peixe-tambaqui-kg",
     "https://portalamazonia.com/wp-content/uploads/2021/05/b2ap3_large_tambaqui-1.jpeg",
     "Portal Amazônia (tambaqui inteiro, referência da espécie)"),
    ("peixe-dourada-kg",
     "https://manatipescados.com.br/wp-content/uploads/2022/07/FILE-DE-DOURADO-470x400.png",
     "Manati Pescados (filé de dourado, peixaria amazônica)"),
    ("sorvete-de-napolitano-tradicional-nestle-pote-15l-un",
     "https://mercantilnovaera.vteximg.com.br/arquivos/ids/216666-800-auto?v=638514797028330000&width=800&height=auto&aspect=true",
     "Nova Era VTEX (pote tradicional napolitano Nestlé 1,5L)"),
    ("sorvete-3-chocolates-lacta-pote-15l-un",
     "https://bompreco.vtexassets.com/arquivos/ids/160539-800-auto?v=637474466028330000&width=800&height=auto&aspect=true",
     "Bom Preço VTEX (pote Lacta 3 Chocolates 1,5L)"),
    ("cafe-em-capsula-de-cafe-filtrado-gourmet-tres-com-10-capsulas-un",
     "https://admintresc.vtexassets.com/arquivos/ids/552549/FILTRADO-GOURMET-C-CAPSULA.png?v=638442112596970000",
     "VTEX oficial 3 Corações (caixa Filtrado Gourmet c/10)"),
    ("biscoito-amori-wafer-mousse-de-limao-un",
     "https://tfchgi.vteximg.com.br/arquivos/ids/157788-1000-1000/7891152800487.jpg?v=637775317909900000",
     "Azul Atacarejo VTEX (caixa Amori Mousse Limão 100g)"),
]

BA = "https://storage.googleapis.com/veja-o-preco.firebasestorage.app"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def baixar(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        return r.content if r.status_code == 200 and len(r.content) > 1000 else None
    except Exception:
        return None


def padrao_400x400(data: bytes) -> io.BytesIO | None:
    """Padrão oficial: 400x400, encaixe proporcional central, fundo branco #FFFFFF, JPEG Q80."""
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        buf = io.BytesIO()
        ImageOps.pad(img, (400, 400), method=Image.LANCZOS, color="white", centering=(0.5, 0.5)).save(
            buf, format="JPEG", quality=80, optimize=True)
        buf.seek(0)
        return buf
    except Exception:
        return None


def main():
    firebase_admin.initialize_app(options={"projectId": "veja-o-preco"})
    db = firestore.client()
    bucket = storage.bucket("veja-o-preco.firebasestorage.app")

    print("=" * 65)
    print(f"🧹 APLICANDO PADRÃO 400x400 às {len(ESCOLHAS)} escolhas visuais")
    print("=" * 65)

    ok = 0
    for prod_id, url, origem in ESCOLHAS:
        print(f"\n📦 {prod_id}")
        print(f"   fonte: {origem}")
        raw = baixar(url)
        if not raw:
            print("   ❌ download falhou — pulando")
            continue
        buf = padrao_400x400(raw)
        if not buf:
            print("   ❌ conversão falhou — pulando")
            continue
        try:
            blob = bucket.blob(f"produtos/{prod_id}.jpg")
            blob.upload_from_file(buf, content_type="image/jpeg")
            blob.make_public()
            url_pub = f"{blob.public_url}?t={int(time.time())}"
            db.collection("produtos").document(prod_id).set({
                "imagem_url": url_pub,
                "imagem_origem": "estudio_400x400",
                "imagem_resolucao": "400x400",
                "imagem_fonte_pesquisa": origem,
                "atualizado_em": datetime.now(),
            }, merge=True)
            ofs = list(db.collection("ofertas").where("produto_id", "==", prod_id).stream())
            for o in ofs:
                db.collection("ofertas").document(o.id).update({
                    "imagem_url": url_pub, "imagem_resolucao": "400x400",
                    "atualizado_em": datetime.now(),
                })
            kb = buf.getbuffer().nbytes / 1024
            print(f"   ✅ 400x400 salvo ({kb:.1f} KB) | {len(ofs)} oferta(s) propagada(s)")
            ok += 1
        except Exception as e:
            print(f"   ❌ upload/backup falhou: {str(e)[:80]}")
        time.sleep(0.6)

    print("\n" + "=" * 65)
    print(f"🏁 CONCLUÍDO: {ok}/{len(ESCOLHAS)} produtos com imagem padrão aplicada")


if __name__ == "__main__":
    main()
