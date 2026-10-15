import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import main


class FakeSnapshot:
    def __init__(self, data=None):
        self.exists = data is not None
        self.data = data or {}

    def to_dict(self):
        return self.data


class FakeRef:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.id = document_id

    def get(self):
        return FakeSnapshot(self.collection.docs.get(self.id))

    def create(self, data):
        if self.id in self.collection.docs:
            raise RuntimeError("already exists")
        self.collection.docs[self.id] = data


class FakeProductDoc:
    def __init__(self, document_id, data):
        self.id = document_id
        self.data = data

    def to_dict(self):
        return self.data


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or {}

    def document(self, document_id):
        return FakeRef(self, document_id)

    def stream(self):
        return [FakeProductDoc(doc_id, data) for doc_id, data in self.docs.items()]


class FakeDB:
    def __init__(self, products):
        self.collections = {
            "produtos": FakeCollection(products),
            "sinonimos": FakeCollection(),
        }

    def collection(self, name):
        return self.collections[name]


class ProductSimilarityTests(unittest.TestCase):
    def setUp(self):
        main._CATALOGO_SIMILARIDADE_CACHE = []
        main._CATALOGO_SIMILARIDADE_ATUALIZADO = 0.0

    def test_maps_high_confidence_name_variation_and_records_percent(self):
        canonical_id = "leite-integral-itambe-1l-un"
        db = FakeDB({canonical_id: {
            "nome": "Leite Integral Itambé 1 litro",
            "unidade": "un",
            "imagem_url": "https://storage.example/curada.jpg",
            "imagem_origem": "curadoria_preview_aprovada",
        }})
        alias_id = "leite-itambe-integral-1l-un"
        result = main.resolver_produto_id_com_sinonimo(
            db, alias_id, "Leite Itambé Integral 1 L", "un"
        )
        self.assertEqual(result, canonical_id)
        alias = db.collection("sinonimos").docs[alias_id]
        self.assertEqual(alias["id_correto"], canonical_id)
        self.assertGreaterEqual(alias["similaridade_pct"], 90)
        self.assertEqual(alias["metodo"], "similaridade_catalogo")

    def test_one_noncritical_word_difference_can_be_learned(self):
        canonical_id = "cafe-lider-tradicional-250g-un"
        db = FakeDB({canonical_id: {
            "nome": "Café Líder Tradicional 250g", "unidade": "un",
        }})
        alias_id = "cafe-lider-torrado-tradicional-250g-un"
        result = main.resolver_produto_id_com_sinonimo(
            db, alias_id, "Café Líder Torrado Tradicional 250g", "un"
        )
        self.assertEqual(result, canonical_id)
        self.assertGreaterEqual(
            db.collection("sinonimos").docs[alias_id]["similaridade_pct"], 88
        )

    def test_different_package_sizes_never_auto_merge(self):
        canonical_id = "arroz-tio-joao-5kg-un"
        db = FakeDB({canonical_id: {
            "nome": "Arroz Tio João 5kg",
            "unidade": "un",
        }})
        result = main.resolver_produto_id_com_sinonimo(
            db, "arroz-tio-joao-1kg-un", "Arroz Tio João 1kg", "un"
        )
        self.assertEqual(result, "arroz-tio-joao-1kg-un")
        self.assertEqual(db.collection("sinonimos").docs, {})

    def test_variant_words_block_auto_merge(self):
        canonical_id = "salsicha-sadia-tradicional-3kg-un"
        db = FakeDB({canonical_id: {
            "nome": "Salsicha Sadia Tradicional 3kg",
            "unidade": "un",
        }})
        result = main.resolver_produto_id_com_sinonimo(
            db, "salsicha-sadia-congelada-3kg-un", "Salsicha Sadia Congelada 3kg", "un"
        )
        self.assertEqual(result, "salsicha-sadia-congelada-3kg-un")
        self.assertEqual(db.collection("sinonimos").docs, {})

    def test_existing_product_id_is_not_auto_redirected(self):
        current_id = "produto-atual-400g-un"
        db = FakeDB({
            current_id: {"nome": "Produto Atual 400g", "unidade": "un"},
            "produto-atual-especial-400g-un": {"nome": "Produto Atual Especial 400g", "unidade": "un"},
        })
        result = main.resolver_produto_id_com_sinonimo(db, current_id, "Produto Atual 400g", "un")
        self.assertEqual(result, current_id)
        self.assertEqual(db.collection("sinonimos").docs, {})

    def test_competing_equally_similar_products_are_left_for_review(self):
        db = FakeDB({
            "arroz-branco-tipo-1-tio-joao-5kg-un": {
                "nome": "Arroz Branco Tipo 1 Tio João 5kg", "unidade": "un",
            },
            "arroz-branco-tipo-1-tio-joao-pacote-5kg-un": {
                "nome": "Arroz Branco Tipo 1 Tio João Pacote 5kg", "unidade": "un",
            },
        })
        alias_id = "arroz-tio-joao-branco-tipo-1-5kg-un"
        result = main.resolver_produto_id_com_sinonimo(
            db, alias_id, "Arroz Tio João Branco Tipo 1 5kg", "un"
        )
        self.assertEqual(result, alias_id)
        self.assertEqual(db.collection("sinonimos").docs, {})

    def test_known_brand_conflict_blocks_auto_merge(self):
        canonical_id = "arroz-tio-joao-tipo-1-5kg-un"
        db = FakeDB({canonical_id: {
            "nome": "Arroz Tio João Tipo 1 5kg", "unidade": "un",
        }})
        alias_id = "arroz-urbano-tio-joao-tipo-1-5kg-un"
        result = main.resolver_produto_id_com_sinonimo(
            db, alias_id, "Arroz Urbano Tio João Tipo 1 5kg", "un"
        )
        self.assertEqual(result, alias_id)
        self.assertEqual(db.collection("sinonimos").docs, {})


if __name__ == "__main__":
    unittest.main()
