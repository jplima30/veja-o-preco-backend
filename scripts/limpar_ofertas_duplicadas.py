#!/usr/bin/env python3
"""
Limpa ofertas duplicadas vigentes: mesmo (produto_id, supermercado_id, preco)
com mais de um documento válido -> mantém só o criado_em mais novo, deleta o resto.
Uso: functions/venv/bin/python3 scripts/limpar_ofertas_duplicadas.py [--apply]
Sem --apply só relata.
"""
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.append(__import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..")))
sys.path.append(__import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "../functions")))

import firebase_admin
from firebase_admin import firestore

APPLY = "--apply" in sys.argv


def main():
    firebase_admin.initialize_app(options={"projectId": "veja-o-preco"})
    db = firestore.client()
    now = datetime.now(timezone.utc)

    grupos = defaultdict(list)
    total = 0
    for o in db.collection("ofertas").stream():
        v = o.to_dict()
        exp = v.get("expira_em")
        if not exp:
            continue
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            continue
        total += 1
        grupos[(v.get("produto_id"), v.get("supermercado_id"), v.get("preco"))].append(
            (v.get("criado_em"), o.id, v.get("produto_nome"))
        )

    print(f"Válidas: {total} | grupos: {len(grupos)}")
    dups = {k: v for k, v in grupos.items() if len(v) > 1}
    print(f"Grupos duplicados: {len(dups)}")
    apagar = []
    for (pid, loja, preco), items in sorted(dups.items()):
        items.sort(key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        keep = items[0]
        print(f"\n{pid} | {loja} | R$ {preco} — {len(items)} docs, mantém {keep[1]}")
        for c, oid, nome in items[1:]:
            print(f"   {'APAGAR' if APPLY else 'apagaria'} {oid} ({c})")
            apagar.append(oid)

    if APPLY and apagar:
        for oid in apagar:
            db.collection("ofertas").document(oid).delete()
        print(f"\n🏁 {len(apagar)} documentos duplicados deletados.")
    elif not APPLY:
        print(f"\n{len(apagar)} docs seriam deletados. Rode com --apply para aplicar.")


if __name__ == "__main__":
    main()
