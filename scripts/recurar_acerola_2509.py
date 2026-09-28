#!/usr/bin/env python3
"""
RE-CURAÇÃO PONTUAL 25/09 — Polpa de Fruta Congelada Acerola Hiper Frutas.
Entrou hoje via CRON com foto de manicure (autopilot adotou a 1ª que baixou).
Escolha visual do agente: packshot Brasfrut Acerola 100g (VTEX Coop) — a marca
exata (Hiper Frutas) não tem packshot público (apenas redes sociais, blocklist).
Aplica o padrão oficial: 400x400 fundo branco #FFFFFF, JPEG Q80, Storage,
/produtos + propagação /ofertas.

Uso: functions/venv/bin/python3 scripts/recurar_acerola_2509.py
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

PRODUTO_ID = "polpa-de-fruta-congelada-acerola-hiper-frutas-un"
URL_ESCOLHIDA = "https://img.freepik.com/fotos-premium/fruta-acerola-vermelha-malpighia-glabra-com-folhas-verdes-isoladas-em-branco_264757-204.jpg"
FONTE = "Foto neutra da fruta acerola (Freepik, isolada em fundo branco) — marca Hiper Frutas sem packshot público (instagram sem post de acerola)"
BA = "https://storage.googleapis.com/veja-o-preco.firebasestorage.app"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def processar_400x400(conteudo: bytes) -> bytes:
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

    r = requests.get(URL_ESCOLHIDA, headers=HEADERS, timeout=25)
    r.raise_for_status()
    jpg = processar_400x400(r.content)

    blob = bucket.blob(f"produtos/{PRODUTO_ID}.jpg")
    blob.upload_from_string(jpg, content_type="image/jpeg")
    blob.make_public()
    nova_url = f"{BA}/produtos/{PRODUTO_ID}.jpg?t={int(time.time())}"

    db.collection("produtos").document(PRODUTO_ID).set({
        "imagem_url": nova_url,
        "imagem_origem": "estudio_400x400",
        "imagem_fonte_pesquisa": FONTE,
        "imagem_atualizada_em": datetime.now(),
    }, merge=True)

    n_of = 0
    for o in db.collection("ofertas").where(
            filter=firestore.FieldFilter("produto_id", "==", PRODUTO_ID)).stream():
        o.reference.set({"imagem_url": nova_url}, merge=True)
        n_of += 1

    print(f"✅ {PRODUTO_ID}  {len(jpg)//1024} KB  ofertas propagadas={n_of}")


if __name__ == "__main__":
    main()
