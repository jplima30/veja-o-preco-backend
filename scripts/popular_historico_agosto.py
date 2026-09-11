#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Carga e Resgate do Histórico Permanente de Preços
Lê o cache de agosto preservado no Preview do Simulador iOS (LevelDB)
e as ofertas vigentes de hoje no Cloud Firestore, populando a coleção permanente `historico_precos`.

Issue: #67
"""

import os
import sys
import glob
import re
from datetime import datetime

# Inclusão dos paths do projeto
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../functions')))

import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.types import Document

def decode_varint(b, pos=0):
    res = 0
    shift = 0
    while True:
        byte = b[pos]
        pos += 1
        res |= (byte & 0x7f) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return res, pos

def value_to_python(val):
    kind = val._pb.WhichOneof('value_type')
    if kind == 'null_value': return None
    elif kind == 'boolean_value': return val.boolean_value
    elif kind == 'integer_value': return val.integer_value
    elif kind == 'double_value': return val.double_value
    elif kind == 'timestamp_value': return val.timestamp_value
    elif kind == 'string_value': return val.string_value
    elif kind == 'reference_value': return val.reference_value
    elif kind == 'map_value': return {k: value_to_python(v) for k, v in val.map_value.fields.items()}
    elif kind == 'array_value': return [value_to_python(v) for v in val.array_value.values]
    return None

def resgatar_cache_preview():
    preview_dir = '/Users/jplima/Library/Developer/Xcode/UserData/Previews/Simulator Devices/55CCE417-2DED-4B3C-9558-3F7AD6881268/data/Containers/Data/Application/179CCCDD-CB47-4B3A-8AE7-58FECDACBF66/Library/Application Support/firestore'
    if not os.path.exists(preview_dir):
        print(f"⚠️ Diretório de cache do Preview não encontrado: {preview_dir}")
        return {}

    files = [f for f in glob.glob(f'{preview_dir}/**/*', recursive=True) if f.endswith('.ldb') or f.endswith('.log')]
    print(f"📂 Lendo {len(files)} arquivos do cache LevelDB do Preview...")

    all_data = b''
    for f in files:
        try:
            with open(f, 'rb') as fp:
                all_data += fp.read()
        except Exception as e:
            print(f"  Aviso ao ler {f}: {e}")

    pattern = re.compile(rb'(projects/[^/]+/databases/\(default\)/documents/ofertas/[a-zA-Z0-9_-]{20})')
    matches = list(pattern.finditer(all_data))
    print(f"🔍 Documentos de ofertas encontrados no stream binário: {len(matches)}")

    ofertas_resgatadas = {}

    for m in matches:
        start = m.start()
        # Localiza o cabeçalho varint do documento
        for backtrack in range(2, 8):
            pos = start - backtrack
            if all_data[pos] == 0x12:
                doc_len, after_len_pos = decode_varint(all_data, pos + 1)
                if after_len_pos == start - 2 and all_data[start - 2] == 0x0a:
                    doc_bytes = all_data[after_len_pos : after_len_pos + doc_len]
                    try:
                        d = Document.deserialize(doc_bytes)
                        fields = {k: value_to_python(v) for k, v in d.fields.items()}
                        
                        produto_id = fields.get('produto_id')
                        preco = fields.get('preco')
                        supermercado_id = fields.get('supermercado_id') or 'desconhecido'
                        
                        if not produto_id or preco is None:
                            continue

                        criado_em = fields.get('criado_em')
                        if isinstance(criado_em, datetime):
                            data_str = criado_em.strftime('%Y-%m-%d')
                        else:
                            data_str = '2026-08-25'

                        historico_id = f"{produto_id}_{supermercado_id}_{data_str}"

                        ofertas_resgatadas[historico_id] = {
                            "produto_id": str(produto_id),
                            "produto_nome": fields.get('produto_nome') or fields.get('nome') or 'Produto sem nome',
                            "supermercado_id": str(supermercado_id),
                            "loja": fields.get('loja') or str(supermercado_id),
                            "preco": float(preco),
                            "preco_antigo": float(fields['preco_antigo']) if fields.get('preco_antigo') is not None else None,
                            "unidade": fields.get('unidade') or 'un',
                            "categoria": fields.get('categoria') or 'DIVERSOS',
                            "data": data_str,
                            "imagem_url": fields.get('imagem_url') or '',
                            "criado_em": criado_em if isinstance(criado_em, datetime) else datetime.now(),
                            "origem": "resgate_preview_agosto"
                        }
                    except Exception:
                        pass
                    break

    print(f"✅ Ofertas de agosto únicas prontas para carga: {len(ofertas_resgatadas)}")
    return ofertas_resgatadas

def carregar_ofertas_hoje(db):
    print("📡 Carregando ofertas vigentes ativas hoje no Firestore...")
    data_hoje_str = datetime.now().strftime("%Y-%m-%d")
    hoje_map = {}
    
    docs = db.collection("ofertas").stream()
    for doc in docs:
        d = doc.to_dict()
        produto_id = d.get('produto_id')
        preco = d.get('preco')
        supermercado_id = d.get('supermercado_id') or 'desconhecido'
        
        if not produto_id or preco is None:
            continue
            
        historico_id = f"{produto_id}_{supermercado_id}_{data_hoje_str}"
        hoje_map[historico_id] = {
            "produto_id": str(produto_id),
            "produto_nome": d.get('produto_nome') or 'Produto sem nome',
            "supermercado_id": str(supermercado_id),
            "loja": d.get('loja') or str(supermercado_id),
            "preco": float(preco),
            "preco_antigo": float(d['preco_antigo']) if d.get('preco_antigo') is not None else None,
            "unidade": d.get('unidade') or 'un',
            "categoria": d.get('categoria') or 'DIVERSOS',
            "data": data_hoje_str,
            "imagem_url": d.get('imagem_url') or '',
            "criado_em": d.get('criado_em') or datetime.now(),
            "origem": "oferta_vigente_hoje"
        }
    print(f"✅ Ofertas vigentes de hoje prontas para carga: {len(hoje_map)}")
    return hoje_map

def salvar_em_lotes(db, registros_map):
    total = len(registros_map)
    if total == 0:
        print("Nenhum registro para salvar.")
        return

    print(f"🚀 Iniciando gravação em lotes (batch.commit()) de {total} cotações em 'historico_precos'...")
    
    batch = db.batch()
    count = 0
    lotes_commitados = 0
    tamanho_lote = 400

    col_ref = db.collection("historico_precos")

    for hid, dados in registros_map.items():
        doc_ref = col_ref.document(hid)
        batch.set(doc_ref, dados, merge=True)
        count += 1

        if count % tamanho_lote == 0:
            batch.commit()
            lotes_commitados += 1
            print(f"  💾 Lote {lotes_commitados} commitado ({count}/{total} docs)...")
            batch = db.batch()

    if count % tamanho_lote != 0:
        batch.commit()
        lotes_commitados += 1
        print(f"  💾 Lote final {lotes_commitados} commitado ({count}/{total} docs)...")

    print(f"✨ Concluída gravação de {total} documentos em {lotes_commitados} lotes!")

def main():
    print("==================================================================")
    print("📈 CARGA DE HISTÓRICO PERMANENTE DE PREÇOS (Issue #67)")
    print("==================================================================")

    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={'projectId': 'veja-o-preco'})
    db = firestore.client()

    # 1. Resgatar ofertas de agosto do cache local
    agosto_map = resgatar_cache_preview()

    # 2. Resgatar ofertas de hoje da coleção /ofertas
    hoje_map = carregar_ofertas_hoje(db)

    # 3. Consolidar todas as cotações
    todos_registros = {}
    todos_registros.update(agosto_map)
    todos_registros.update(hoje_map)

    print(f"\n📊 Total consolidado para popular 'historico_precos': {len(todos_registros)} cotações únicas")

    # 4. Salvar no Firestore
    salvar_em_lotes(db, todos_registros)

    # 5. Auditoria de Contagem Final
    count_query = db.collection("historico_precos").count()
    total_banco = count_query.get()[0][0].value
    print(f"\n🏆 Total de cotações agora existentes na coleção 'historico_precos': {total_banco}")
    print("==================================================================")

if __name__ == '__main__':
    main()
