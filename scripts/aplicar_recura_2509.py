#!/usr/bin/env python3
"""
RECURA 25/09 — ETAPA 2 (aplicação).
As URLs abaixo foram PESQUISADAS (3 subagentes, só URLs HTTP 200 verificadas)
e ESCOLHIDAS visualmente pelo agente (15/15 inspecionadas em galeria local).
Este script aplica o PADRÃO OFICIAL do projeto a cada escolha:
  download -> 400x400 fundo branco #FFFFFF (JPEG Q80) -> Storage
  -> /produtos (imagem_url, origem=estudio_400x400, imagem_fonte_pesquisa)
  -> propaga /ofertas.

Uso: functions/venv/bin/python3 scripts/aplicar_recura_2509.py
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
    # ── Lote 25/09 (CRONs de hoje) ──
    ("capsula-nescafe-dolce-gusto-varios-sabores-170g-un",
     "https://mambodelivery.vteximg.com.br/arquivos/ids/249649/7891000243688_1.jpg?v=639148123140770000",
     "Mambo VTEX (caixa Nescau Dolce Gusto 10un 170g — sem SKU 'vários sabores', mono-sabor Nescau é o correto)"),
    ("capsula-nescafe-dolce-gusto-un",
     "https://mambodelivery.vteximg.com.br/arquivos/ids/249649/7891000243688_1.jpg?v=639148123140770000",
     "Mambo VTEX (caixa Nescau Dolce Gusto 10un — antes: foto de remédio)"),
    ("chocolate-em-barra-garoto-varios-sabores-80g-un",
     "https://savegnagoio.vteximg.com.br/arquivos/ids/448278/ChocolateGarotoAoLeiteTablete80g1.jpg?v=638525415125770000",
     "Savegnago VTEX (tablete Garoto Ao Leite 80g — antes: barras gringas)"),
    ("chocolate-em-barra-nestle-varios-sabores-80g90g-un",
     "https://savegnagoio.vteximg.com.br/arquivos/ids/449188/ChocolateNestleClassicAoLeiteTab1.jpg?v=638527588496970000",
     "Savegnago VTEX (tablete Nestlé Classic 80g — antes: flatlay genérico)"),
    ("nutren-nestle-kids-varios-sabores-350g-un",
     "https://savegnagoio.vteximg.com.br/arquivos/ids/451243/ComplementoAlimentarNutrenKidsCho1.jpg?v=638611363946900000",
     "Savegnago VTEX (lata Nutren Kids 350g — antes: whey Protein adulto)"),
    ("shampoo-bio-extratus-equilibrio-250ml-un",
     "https://bioextratusvirtual.vteximg.com.br/arquivos/ids/160377/Shampoo-250mL-Equlibrio.jpg?v=638005971032430000",
     "Site oficial Bio Extratus (frasco Equilíbrio 250ml — antes: hotlink VipCommerce quebrado)"),
    ("rosquinha-jasmine-cenoura-mel-light-150gr-un",
     "https://covabra.vteximg.com.br/arquivos/ids/557947/10763.jpg?v=638925508800900000",
     "Covabra VTEX (Rosquinha Jasmine Zero Laranja/Cenoura 120g — produto Light 150g aparenta descontinuado, mais próximo; antes: hotlink quebrado)"),
    # ── Lote 24/09 (CRON de ontem, conferidas ontem) ──
    ("ave-fiesta-seara-un",
     "https://savegnagoio.vteximg.com.br/arquivos/ids/462328/AveFiestaTemperadaSeara38kg1.jpg?v=638701499449570000",
     "Savegnago VTEX (Ave Fiesta Temperada Seara — antes: foto de pássaro)"),
    ("leite-condensado-nestle-un",
     "https://savegnagoio.vteximg.com.br/arquivos/ids/493788/LeiteCondensadoMocaTradicionalLat1.jpg?v=639183296256330000",
     "Savegnago VTEX (lata Moça 395g — antes: leite genérico despejado)"),
    ("nescau-nestle-un",
     "https://covabra.vteximg.com.br/arquivos/ids/552885/108464.jpg?v=638925463126900000",
     "Covabra VTEX (lata Nescau 350g — antes: novelo de lã)"),
    ("biscoito-choco-biscuit-nestle-un",
     "https://covabra.vteximg.com.br/arquivos/ids/576036/7891000402979-BiscoitocomChocolateChocobiscuitNESTLEAoLeite78g-1.jpg.jpg?v=639167798772800000",
     "Covabra VTEX (Choco Biscuit ao leite 78g — antes: cookies genéricos)"),
    ("biscoito-choco-biscuit-nestle-78g-un",
     "https://covabra.vteximg.com.br/arquivos/ids/576036/7891000402979-BiscoitocomChocolateChocobiscuitNESTLEAoLeite78g-1.jpg.jpg?v=639167798772800000",
     "Covabra VTEX (mesmo produto do base — unificação visual)"),
    ("biscoito-choco-biscuit-nestle-ao-leite-78g-un",
     "https://covabra.vteximg.com.br/arquivos/ids/576036/7891000402979-BiscoitocomChocolateChocobiscuitNESTLEAoLeite78g-1.jpg.jpg?v=639167798772800000",
     "Covabra VTEX (mesmo produto do base — unificação visual)"),
    ("protetor-solar-principia-fps-60-un",
     "https://cdn.principiaskin.com/media/catalog/product/cache/a11fc81ad62814be31cd922a993aa5ec/p/r/principia-skincare-protetor-solar-facial-ps-02-60fps-filtros-uv-niacinamida-1.jpg",
     "Site oficial Principia (PS-02 FPS 60 — antes: homem de polo)"),
    ("protetor-solar-principia-fps-35-un",
     "https://cdn.principiaskin.com/media/catalog/product/cache/a11fc81ad62814be31cd922a993aa5ec/p/r/principia-skincare-protetor-solar-facial-ps-02-60fps-filtros-uv-niacinamida-1.jpg",
     "Site oficial Principia (RESSALVA: imagem é do FPS 60, linha correta mas FPS difere)"),
    ("protetor-solar-principia-fps-99-un",
     "https://cdn.principiaskin.com/media/catalog/product/cache/a11fc81ad62814be31cd922a993aa5ec/p/r/principia-skincare-protetor-solar-facial-ps-02-60fps-filtros-uv-niacinamida-1.jpg",
     "Site oficial Principia (RESSALVA: imagem é do FPS 60, linha correta mas FPS difere)"),
    ("protetor-solar-principia-un",
     "https://cdn.principiaskin.com/media/catalog/product/cache/a11fc81ad62814be31cd922a993aa5ec/p/r/principia-skincare-protetor-solar-facial-ps-02-60fps-filtros-uv-niacinamida-1.jpg",
     "Site oficial Principia (linha correta — antes: homem de polo)"),
    ("tucupi-artesanal-concentrado-un",
     "https://atacadaobr.vteximg.com.br/arquivos/ids/1498542/g.jpg.jpg?v=639216025944130000",
     "Atacadão VTEX (Molho Tucupi Pai D'égua 500ml — antes: frasco de laboratório)"),
    ("tucupi-va-artesanal-un",
     "https://covabra.vteximg.com.br/arquivos/ids/540492/110070.jpg?v=638925337966800000",
     "Covabra VTEX (Manioca Tucupi Amarelo 300ml, marca artesanal do Pará)"),
    ("picanha-suina-sulita-kg",
     "https://sulita.com.br/wp-content/uploads/2020/01/Picanha-Gourmet-Sulita_site.png",
     "Site oficial Sulita (Picanha Gourmet, marca exata — foto do verso da embalagem; antes: corte que parecia brisket bovino)"),
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
    print(f"🧹 APLICANDO PADRÃO 400x400 às {len(ESCOLHAS)} escolhas visuais (recura 25/09)")
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
