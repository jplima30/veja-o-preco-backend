#!/usr/bin/env python3
"""
SANEAMENTO 23/09: recura validada das 15 imagens erradas/quebradas/dúbias
do lote do CRON de hoje. Padrão do projeto (fixar_imagens_inconsistentes):
busca Google Imagens via Playwright + fallback Bing, valida cada candidata
com Gemini Vision (título ↔ imagem) ANTES do upload, packshot 400x400 fundo
branco, propagação para /produtos e /ofertas.

Os 6 produtos automotivos Proauto NÃO são curados: devem ser removidos
(violam Food Only). Tratamento à parte.

Uso: functions/venv/bin/python3 scripts/sanear_lote_2309.py
"""

import os
import sys
import time
import requests
from datetime import datetime
from google import genai
from google.genai import types
from playwright.sync_api import sync_playwright

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.central_imagens import (
    inicializar_firebase,
    limpar_termo_busca,
    processar_e_otimizar_imagem,
    buscar_google_images_playwright,
)
from scripts.curar_lote_alta_fidelidade import buscar_candidatos_bing

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "veja-o-preco")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
MODEL = "gemini-3.1-flash-lite"
RELATORIO_JSON = "auditoria_visual/AUDITORIA_IMAGENS/saneamento_2026-09-23.json"
RELATORIO_MD = "auditoria_visual/AUDITORIA_IMAGENS/saneamento_2026-09-23.md"

# (produto_id, nome oficial, [queries sob medida — desambiguação])
# Queries com sufixo "embalagem"/"packshot" e exclusões quando o termo é ambíguo.
ALVOS = [
    ("rap-10-integral-pullman-330g-un", "Rap 10 Integral Pullman 330g",
     ["Rap 10 Integral Pullman embalagem", "Rap 10 Pullman pão folha integral pacote"]),
    ("azeite-extra-virgem-grego-mykonos-500ml-un", "Azeite Extra Virgem Grego Mykonos 500ml",
     ["Azeite Extra Virgem Mykonos 500ml garrafa", "Mykonos azeite grego extra virgem embalagem"]),
    ("torrada-marilan-magic-toast-inegral-110g-un", "Torrada Marilan Magic Toast Integral 110g",
     ["Torrada Marilan Magic Toast embalagem", "Marilan Magic Toast integral pacote"]),
    ("canela-em-po-br-spices-50g-un", "Canela em Pó BR Spices 50g",
     ["Canela em pó BR Spices pote 50g", "BR Spices temperos embalagem canela"]),
    ("tempero-para-hamburguer-heinz-80g-un", "Tempero Para Hambúrguer Heinz 80g",
     ["Tempero para Hambúrguer Heinz 80g", "Heinz tempero hambúrguer frasco"]),
    ("creme-dental-tandy-uvaventura-50g-un", "Creme Dental Tandy Uvaventura 50g",
     ["Creme Dental Tandy Uvaventura embalagem", "Tandy Uvaventura pasta de dente"]),
    ("cappuccino-santa-clara-classic-gf-26o-ml-un", "Cappuccino Santa Clara Classic 260ml",
     ["Cappuccino Santa Clara Classic garrafa 260ml", "Santa Clara cappuccino ready to drink"]),
    ("melao-pele-de-sapo-kg", "Melão Pele de Sapo",
     ["melão pele de sapo fruta inteira", "melón piel de sapo"]),
    ("peixe-tambaqui-kg", "Peixe Tambaqui",
     ["tambaqui peixe amazônico", "tambaqui peixe inteiro"]),
    ("peixe-dourada-kg", "Peixe Dourada",
     ["dourada peixe amazônico água doce", "peixe dourado amazônico inteiro"]),
    ("sorvete-de-napolitano-tradicional-nestle-pote-15l-un", "Sorvete De Napolitano Tradicional Nestle Pote 1.5l",
     ["Sorvete Napolitano Nestlé pote 1.5L embalagem", "Nestlé sorvete napolitano pote"]),
    ("sorvete-3-chocolates-lacta-pote-15l-un", "Sorvete 3 Chocolates Lacta Pote 1.5l",
     ["Sorvete 3 Chocolates Lactá pote 1.5L", "Lacta sorvete pote chocolates embalagem"]),
    ("cafe-em-capsula-de-cafe-filtrado-gourmet-tres-com-10-capsulas-un", "Café Em Cápsula Filtrado Gourmet Tres Com 10 Cápsulas",
     ["Cápsula Três Corações Filtrado Gourmet", "Tres corações cápsulas filtrado embalagem"]),
    ("biscoito-amori-wafer-mousse-de-limao-un", "Biscoito Amori Wafer Mousse De Limao",
     ["Biscoito Amori wafer limão embalagem", "Amori wafer mousse de limão pacote"]),
    ("pao-de-forma-massa-e-forno-un", "Pão de Forma Massa e Forno",
     ["Pão de forma Massa e Forno embalagem", "pão de forma fatiado pacote massa forno"]),
]

PROMPT = """Você é um auditor de qualidade de imagens para um aplicativo de supermercado.

Produto esperado no título: "{nome}"

Analise visualmente a imagem e responda SOMENTE em JSON:
{{
  "consistente": true,
  "confianca": "ALTA",
  "o_que_vejo": "descrição curta do produto na imagem",
  "problema": null
}}

Regras:
- consistente=false se: produto errado, marca diferente da esperada, categoria diferente, texto do rótulo contradiz o título, imagem com colagem de encarte/preço/nome de outro produto, ou imagem que não mostra o produto esperado
- consistente=true mesmo que seja foto genérica/ilustrativa do produto correto (ex: fruta/peixe fresco sem embalagem)
- confianca: ALTA (certeza), MEDIA (dúvida razoável), BAIXA (imagem ruim/obscura)
- problema: null se consistente, caso contrário descreva o problema em 1 frase

Responda APENAS o JSON puro, sem markdown."""


def validar_candidata(nome: str, img_bytes: bytes, client) -> dict:
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                PROMPT.format(nome=nome),
            ],
        )
        texto = resp.text.strip()
        if "```" in texto:
            for p in texto.split("```"):
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                if p.startswith("{"):
                    texto = p
                    break
        return json.loads(texto)
    except Exception as e:
        return {"consistente": None, "confianca": "ERRO", "o_que_vejo": "erro", "problema": str(e)}


def baixar(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
        return r.content if r.status_code == 200 else None
    except Exception:
        return None


def main():
    import json
    print("=" * 65)
    print(f"🔧 SANEAMENTO 23/09 — recura validada de {len(ALVOS)} produtos")
    print("=" * 65)
    db, bucket = inicializar_firebase()
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    print("✅ Firebase + Vertex AI conectados\n")

    os.makedirs(os.path.dirname(RELATORIO_JSON), exist_ok=True)
    resultados = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        for idx, (prod_id, nome, queries) in enumerate(ALVOS, 1):
            print(f"\n--- [{idx}/{len(ALVOS)}] {nome} ---")
            termo = limpar_termo_busca(nome)
            urls, vistos = [], set()
            for q in queries:
                g = []
                try:
                    g = buscar_google_images_playwright(q, page=page, max_resultados=6)
                except Exception as e:
                    print(f"   ⚠️ Google falhou ({str(e)[:60]}), seguindo só Bing")
                bing = buscar_candidatos_bing(page, q)
                if not bing and len(q.split()) > 3:
                    bing = buscar_candidatos_bing(page, " ".join(q.split()[:3]))
                for u in g + bing:
                    if u not in vistos:
                        vistos.add(u)
                        urls.append(u)
                print(f"   query '{q}': {len(g)} Google + {len(bing)} Bing")
                if len(urls) >= 12:
                    break
            urls = urls[:16]
            print(f"   {len(urls)} candidatas únicas")

            status, detalhe, aprovada_conf, ofertas = "FALHA", "sem candidata aprovada", "", 0
            for u in urls:
                img = baixar(u)
                if not img:
                    continue
                v = validar_candidata(nome, img, client)
                time.sleep(1.2)
                if v.get("consistente") is True and v.get("confianca") in ("ALTA", "MEDIA"):
                    buf = processar_e_otimizar_imagem(u, tamanho=(400, 400), qualidade=80)
                    if not buf:
                        continue
                    blob = bucket.blob(f"produtos/{prod_id}.jpg")
                    blob.upload_from_file(buf, content_type="image/jpeg")
                    blob.make_public()
                    url_pub = f"{blob.public_url}?t={int(time.time())}"
                    db.collection("produtos").document(prod_id).set({
                        "imagem_url": url_pub, "imagem_origem": "estudio_400x400",
                        "imagem_resolucao": "400x400", "atualizado_em": datetime.now(),
                    }, merge=True)
                    ofs = list(db.collection("ofertas").where("produto_id", "==", prod_id).stream())
                    for o in ofs:
                        db.collection("ofertas").document(o.id).update({
                            "imagem_url": url_pub, "imagem_resolucao": "400x400",
                            "atualizado_em": datetime.now(),
                        })
                    status = "OK"
                    detalhe = str(v.get("o_que_vejo", "?"))[:70]
                    aprovada_conf = v.get("confianca", "")
                    ofertas = len(ofs)
                    print(f"   ✅ APROVADA ({aprovada_conf}): {u[:70]}")
                    break
                print(f"   ⏭️ rejeitada ({v.get('confianca','?')}): {str(v.get('problema','?'))[:60]}")
            print(f"   [{status}] {detalhe} | ofertas: {ofertas}")
            resultados.append({
                "produto_id": prod_id, "nome": nome, "status": status,
                "detalhe": detalhe, "confianca": aprovada_conf, "ofertas": ofertas,
            })
            time.sleep(1)
        browser.close()

    ok = sum(1 for r in resultados if r["status"] == "OK")
    with open(RELATORIO_JSON, "w", encoding="utf-8") as f:
        json.dump({"total": len(resultados), "curados": ok,
                   "falhas": len(resultados) - ok, "detalhes": resultados},
                  f, ensure_ascii=False, indent=2)
    with open(RELATORIO_MD, "w", encoding="utf-8") as f:
        f.write("# Saneamento do lote 23/09 — recura validada\n\n")
        f.write(f"✅ Curados: {ok}/{len(resultados)}\n\n")
        f.write("| Produto | Status | Conf. | Detalhe | Ofertas |\n|---|---|---|---|---|\n")
        for r in resultados:
            f.write(f"| {r['nome']} | {r['status']} | {r['confianca']} | {r['detalhe']} | {r['ofertas']} |\n")
    print("\n" + "=" * 65)
    print(f"🏁 SANEAMENTO: {ok}/{len(resultados)} curados")
    print(f"💾 {RELATORIO_JSON}")


if __name__ == "__main__":
    main()
