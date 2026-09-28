#!/usr/bin/env python3
"""
FIXER: recura os 14 produtos apontados pela auditoria de consistência.
Para cada produto: busca packshot (Bing + domínios varejo), valida cada
candidata com Gemini Vision (título ↔ imagem) e só faz upload da primeira
APROVADA. Padrão 400x400 fundo branco + propagação p/ ofertas.
Uso: functions/venv/bin/python3 scripts/fixar_imagens_inconsistentes.py
"""

import os
import sys
import io
import json
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
RELATORIO_JSON = "auditoria_visual/AUDITORIA_IMAGENS/fix_2026-09-17.json"
RELATORIO_MD = "auditoria_visual/AUDITORIA_IMAGENS/fix_2026-09-17.md"

# Já curados nos rounds 1–2 — pulados no round 3
CURADOS_OK = {"morango-easychef-101kg-un",
              "frango-avispara-in-natura-congelado-kg",
              "absorvente-noturno-always-un"}

# Queries sob medida (round 3): embalagem + desambiguação via exclusões
CONSULTAS = {
    "pano-multiuso-perfex-un": ["Pano Multiuso Perfex embalagem", "Pano Multiuso Perfex pacote"],
    "locao-hidratante-nivea-200ml-un": ["Loção Hidratante Nivea 200ml embalagem", "Nivea loção hidratante pele 200ml frasco"],
    "chocolate-caribe-baton-chocstisk-garoto-24g-un": ["Chocolate Baton Garoto tablete embalagem", "Baton Garoto chocolate ao leite"],
    "bebida-lactea-nestle-sabores-270ml-un": ["Bebida Láctea Nestlé 270ml garrafinha", "Nestlé bebida láctea sabores embalagem"],
    "feijao-preto-dona-de-1kg-un": ["Feijão Preto Dona Dé 1kg pacote", "Feijão Dona Dé embalagem"],
    "margarina-primor-15kg-un": ["Margarina Primor 15kg balde", "Margarina Primor embalagem industrial"],
    "desodor-pd-brisa-floral-40g-un": ['Desodorante corporal Brisa Floral -ruína -monumento -pedra', "Desodorante Brisa Floral antitranspirante"],
    "sabonete-liquido-johnsons-baby-un": ["Sabonete Líquido Johnson Baby frasco -granado -barra", "Johnson Baby sabonete líquido infantil"],
    "biscoito-de-leite-passatempo-nestle-150g-un": ["Biscoito Passatempo Nestlé pacote -cérebro -anatomia", "Passatempo Nestlé biscoito recheado"],
    "detergente-ype-5l-un": ["Detergente Ypê 5L galão -MAS -Ace -Magia", "Ypê detergente líquido galão"],
    "racao-vittamax-peixe-ou-mix-1kg-un": ["Ração VittaMax cães pacote -treliça -planilha", "VittaMax ração Mix 1kg"],
}

# (produto_id, nome oficial) — os 14 inconsistentes da auditoria 2026-09-17
ALVOS = [
    ("pano-multiuso-perfex-un", "Pano Multiuso Perfex"),
    ("locao-hidratante-nivea-200ml-un", "Loção Hidratante Nivea 200ml"),
    ("chocolate-caribe-baton-chocstisk-garoto-24g-un", "Chocolate Caribe Baton Chocstisk Garoto 24g"),
    ("bebida-lactea-nestle-sabores-270ml-un", "Bebida Láctea Nestlé Sabores 270ml"),
    ("feijao-preto-dona-de-1kg-un", "Feijão Preto Dona Dé 1kg"),
    ("margarina-primor-15kg-un", "Margarina Primor 15kg"),
    ("frango-avispara-in-natura-congelado-kg", "Frango Avispará in Natura Congelado"),
    ("desodor-pd-brisa-floral-40g-un", "Desodorante Brisa Floral 40g"),
    ("absorvente-noturno-always-un", "Absorvente Noturno Always"),
    ("sabonete-liquido-johnsons-baby-un", "Sabonete Líquido Johnsons Baby"),
    ("biscoito-de-leite-passatempo-nestle-150g-un", "Biscoito de Leite Passatempo Nestlé 150g"),
    ("detergente-ype-5l-un", "Detergente Ypê 5L"),
    ("racao-vittamax-peixe-ou-mix-1kg-un", "Ração VittaMax Peixe ou Mix 1kg"),
    ("morango-easychef-101kg-un", "Morango Easychef 1,01kg"),
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
- consistente=false se: produto errado, marca diferente da esperada, categoria diferente, texto do rótulo contradiz o título
- consistente=true mesmo que seja foto genérica/ilustrativa do produto correto
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
        r = requests.get(url, timeout=12)
        return r.content if r.status_code == 200 else None
    except Exception:
        return None


def main():
    print("=" * 65)
    print(f"🔧 FIXER: recura validada dos {len(ALVOS)} inconsistentes")
    print("=" * 65)
    db, bucket = inicializar_firebase()
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    print("✅ Firebase + Vertex AI conectados\n")

    resultados = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        for idx, (prod_id, nome) in enumerate(ALVOS, 1):
            if prod_id in CURADOS_OK:
                print(f"\n--- [{idx}/{len(ALVOS)}] {nome} — já curado, pulando ---")
                resultados.append({"produto_id": prod_id, "nome": nome,
                                   "status": "OK-ANT", "detalhe": "curado round 1", "ofertas": 0})
                continue
            print(f"\n--- [{idx}/{len(ALVOS)}] {nome} ---")
            termo = limpar_termo_busca(nome)
            queries = CONSULTAS.get(prod_id, [termo])
            # Google primeiro (melhor ranking de packshots), Bing de fallback
            urls = []
            vistos = set()
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
            status, detalhe, ofertas = "FALHA", "sem candidata aprovada", 0
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
                    status, detalhe, ofertas = "OK", f"{v.get('o_que_vejo','?')[:70]}", len(ofs)
                    print(f"   ✅ APROVADA ({v.get('confianca')}): {u[:70]}")
                    break
                print(f"   ⏭️ rejeitada ({v.get('confianca')}): {v.get('problema','?')[:60]}")
            print(f"   [{status}] {detalhe} | ofertas: {ofertas}")
            resultados.append({"produto_id": prod_id, "nome": nome,
                               "status": status, "detalhe": detalhe, "ofertas": ofertas})
            time.sleep(1)
        browser.close()

    ok = sum(1 for r in resultados if r["status"] == "OK")
    base = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(base, RELATORIO_JSON), "w", encoding="utf-8") as f:
        json.dump({"total": len(resultados), "curados": ok,
                   "falhas": len(resultados) - ok, "detalhes": resultados},
                  f, ensure_ascii=False, indent=2)
    with open(os.path.join(base, RELATORIO_MD), "w", encoding="utf-8") as f:
        f.write("# Fixer — recura validada 2026-09-17\n\n")
        f.write(f"✅ Curados: {ok}/{len(resultados)}\n\n")
        f.write("| Produto | Status | Detalhe | Ofertas |\n|---|---|---|---|\n")
        for r in resultados:
            f.write(f"| {r['nome']} | {r['status']} | {r['detalhe']} | {r['ofertas']} |\n")
    print("\n" + "=" * 65)
    print(f"🏁 FIXER: {ok}/{len(resultados)} curados")
    print(f"💾 {RELATORIO_JSON}")


if __name__ == "__main__":
    main()
