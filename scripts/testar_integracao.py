"""
Script: testar_integracao.py
Objetivo: Testar ponta-a-ponta a integração scraper → Firestore
           SEM passar pelo emulador (que tem sandbox de DNS).

Como rodar:
    source functions/venv/bin/activate
    python3 scripts/testar_integracao.py
"""

import sys
import os
import json
import re
import requests
from datetime import datetime, timedelta

# --- Inicialização do Firebase Admin (igual ao main.py) ---
import firebase_admin
from firebase_admin import firestore

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={"projectId": "veja-o-preco"})

db = firestore.client()

# ══════════════════════════════════════════════════
# Funções utilitárias (replicadas do main.py)
# ══════════════════════════════════════════════════

def normalizar_nome(nome: str, unidade: str = "") -> str:
    texto = f"{nome} {unidade}".strip().lower()
    texto = re.sub(r"[áàãâ]", "a", texto)
    texto = re.sub(r"[éê]", "e", texto)
    texto = re.sub(r"[íî]", "i", texto)
    texto = re.sub(r"[óõô]", "o", texto)
    texto = re.sub(r"[úü]", "u", texto)
    texto = re.sub(r"[ç]", "c", texto)
    texto = re.sub(r"[^a-z0-9\s]", "", texto)
    texto = re.sub(r"\s+", "-", texto.strip())
    return texto[:100]

def buscar_imagem(nome: str, imagem_api: str = "") -> str:
    if imagem_api and imagem_api.startswith("http"):
        return imagem_api
    try:
        query = nome.split(" ")[0]
        url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&json=1&page_size=1"
        r = requests.get(url, timeout=5)
        produtos = r.json().get("products", [])
        if produtos and produtos[0].get("image_url"):
            return produtos[0]["image_url"]
    except:
        pass
    return ""

def salvar_produto_e_oferta(nome: str, preco: float, unidade: str,
                             supermercado_id: str, loja: str,
                             categoria: str = "Geral", imagem_api: str = "",
                             validade: datetime = None):
    if not nome or preco <= 0:
        return

    produto_id = normalizar_nome(nome, unidade)
    imagem = buscar_imagem(nome, imagem_api)

    # Upsert em /produtos
    ref_produto = db.collection("produtos").document(produto_id)
    doc = ref_produto.get()
    if not doc.exists:
        ref_produto.set({
            "nome": nome,
            "produto_id": produto_id,
            "unidade": unidade,
            "categoria": categoria,
            "imagem": imagem,
            "criado_em": datetime.utcnow(),
            "atualizado_em": datetime.utcnow(),
        })
        print(f"  ✅ NOVO produto: {produto_id}")
    else:
        updates = {"atualizado_em": datetime.utcnow()}
        if imagem and not doc.to_dict().get("imagem"):
            updates["imagem"] = imagem
        ref_produto.update(updates)
        print(f"  ♻️  Atualizado: {produto_id}")

    # Nova entrada em /ofertas
    expira_em = validade or (datetime.utcnow() + timedelta(days=7))
    db.collection("ofertas").add({
        "produto_id": produto_id,
        "produto_nome": nome,
        "supermercado_id": supermercado_id,
        "loja": loja,
        "preco": preco,
        "unidade": unidade,
        "categoria": categoria,
        "imagem": imagem,
        "criado_em": datetime.utcnow(),
        "expira_em": expira_em,
    })
    print(f"  💰 Oferta salva: R$ {preco:.2f} ({loja})")

# ══════════════════════════════════════════════════
# TESTE: Seja Econômico → Firestore
# ══════════════════════════════════════════════════

def testar_economico():
    print("\n🔍 Buscando produtos na API do Seja Econômico...")

    url_api = "https://services.vipcommerce.com.br/api-admin/v1/org/315/filial/1/centro_distribuicao/1/loja/produtos/em-oferta"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.grupoeconomico.com.br/ofertas",
        "Origin": "https://www.grupoeconomico.com.br",
        "DomainKey": "grupoeconomico.com.br",
        "OrganizationId": "315",
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NzY3MTc0ODMsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMzE1In0.VsuwHCwfq-CF9yUzkGv6ekV--zAMmtWtPm-H6dbazQvC6GYp5spDx32GlWJEogReqDKU_TWscSNRW070elQDPA"
    }

    params = {"page": "1"}
    response = requests.get(url_api, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    dados = response.json()

    # Detectar chave dos produtos
    chaves = list(dados.keys())
    print(f"  Chaves encontradas: {chaves}")

    # Mesma lógica do main.py para navegar na estrutura
    produtos_raw = []
    if isinstance(dados, list):
        produtos_raw = dados
    elif "data" in dados:
        produtos_raw = dados["data"]
        if isinstance(produtos_raw, dict):
            produtos_raw = produtos_raw.get("produtos", produtos_raw.get("itens", []))
    elif "produtos" in dados:
        produtos_raw = dados["produtos"]

    if isinstance(produtos_raw, dict) and "items" in produtos_raw:
        produtos_raw = produtos_raw["items"]

    if not isinstance(produtos_raw, list):
        print(f"  ⚠️ Estrutura inesperada: {type(produtos_raw)}")
        produtos_raw = []

    print(f"  Total de produtos recebidos: {len(produtos_raw)}")

    # Limitar a 3 produtos para o teste
    produtos_teste = produtos_raw[:3]
    print(f"\n📦 Salvando {len(produtos_teste)} produtos no Firestore (teste)...\n")

    for p in produtos_teste:
        try:
            # Campos VipCommerce (mesma lógica do main.py)
            nome = p.get("descricao") or p.get("nome") or p.get("produto") or ""
            preco = float(p.get("preco_venda") or p.get("preco") or 0)

            if p.get("preco_promocional") and float(p.get("preco_promocional")) > 0:
                preco = float(p.get("preco_promocional"))

            unidade = p.get("unidade", "un")

            # Imagem VipCommerce CDN
            img_file = p.get("imagem_principal") or p.get("imagem") or ""
            imagem = f"https://static.vipcommerce.com.br/img/produtos/315/v/{img_file}" if img_file else ""

            print(f"→ {nome} | R$ {preco:.2f} | {unidade}")
            salvar_produto_e_oferta(
                nome=nome,
                preco=preco,
                unidade=unidade,
                supermercado_id="seja-economico-am",
                loja="Seja Econômico",
                categoria="Geral",
                imagem_api=imagem,
            )
        except Exception as e:
            print(f"  ⚠️  Erro: {e}")

    print("\n✅ Teste concluído! Verifique /produtos e /ofertas no Console do Firebase.")
    print("   https://console.firebase.google.com/project/veja-o-preco/firestore/data/produtos")

if __name__ == "__main__":
    testar_economico()
