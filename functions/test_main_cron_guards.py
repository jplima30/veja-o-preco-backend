import io
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import main


class FakeSnapshot:
    def __init__(self, data=None):
        self.exists = data is not None
        self._data = data or {}

    def to_dict(self):
        return self._data


class FakeProductRef:
    def __init__(self, data=None):
        self.snapshot = FakeSnapshot(data)
        self.updates = []
        self.sets = []

    def get(self):
        return self.snapshot

    def update(self, data):
        self.updates.append(data)

    def set(self, data, **kwargs):
        self.sets.append((data, kwargs))


class FakeOfferRef:
    def __init__(self, data):
        self.data = data
        self.updates = []
        self.deleted = False

    def update(self, data):
        self.updates.append(data)

    def delete(self):
        self.deleted = True


class FakeOfferSnapshot:
    def __init__(self, ref, data):
        self.reference = ref
        self._data = data

    def to_dict(self):
        return self._data


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self._document_id = None
        self.docs_by_id = {}

    def document(self, document_id):
        self._document_id = document_id
        return self.docs_by_id.setdefault(document_id, FakeProductRef())

    def where(self, *_args, **_kwargs):
        return self

    def stream(self):
        return self.docs


class FakeDB:
    def __init__(self, product_data=None, offer_docs=None):
        self.product_ref = FakeProductRef(product_data)
        self.offer_collection = FakeCollection(offer_docs)
        self.history_ref = FakeProductRef()

    def collection(self, name):
        if name == "produtos":
            return _SingleDocCollection(self.product_ref)
        if name == "ofertas":
            return self.offer_collection
        if name == "historico_precos":
            return _SingleDocCollection(self.history_ref)
        return _SingleDocCollection(FakeProductRef())


class _SingleDocCollection:
    def __init__(self, ref):
        self.ref = ref

    def document(self, _document_id):
        return self.ref


class FakeBlob:
    def __init__(self, fail_upload=False):
        self.fail_upload = fail_upload
        self.upload_args = None
        self.reloaded = False
        self.made_public = False
        self.public_url = "https://storage.googleapis.com/test-bucket/produtos/test.jpg"

    def upload_from_string(self, data, **kwargs):
        if self.fail_upload:
            error = RuntimeError("precondition failed")
            error.code = 412
            raise error
        self.upload_args = (data, kwargs)

    def reload(self):
        self.reloaded = True

    def make_public(self):
        self.made_public = True


class CronGuardTests(unittest.TestCase):
    def test_existing_product_image_is_reused_without_storage_write(self):
        db = FakeDB({"imagem_url": "https://example.test/curada.jpg"})
        with patch.object(main, "get_db", return_value=db), \
             patch.object(main, "resolver_produto_id_com_sinonimo", side_effect=lambda _db, pid, *_args: pid), \
             patch.object(main.storage, "bucket") as bucket:
            result = main.upload_imagem_cortada(b"not-needed", [0, 0, 1000, 1000], "test")

        self.assertEqual(result, "https://example.test/curada.jpg")
        bucket.assert_not_called()

    def test_new_image_upload_is_create_only(self):
        db = FakeDB()
        blob = FakeBlob()
        bucket = type("Bucket", (), {"blob": lambda _self, _name: blob})()
        img = Image.new("RGB", (32, 32), "red")
        data = io.BytesIO()
        img.save(data, format="JPEG")

        with patch.object(main, "get_db", return_value=db), \
             patch.object(main, "resolver_produto_id_com_sinonimo", side_effect=lambda _db, pid, *_args: pid), \
             patch.object(main.storage, "bucket", return_value=bucket), \
             patch.object(main.os, "makedirs", side_effect=OSError("skip local audit copy")):
            result = main.upload_imagem_cortada(
                data.getvalue(), [0, 0, 1000, 1000], "test", imagem_validada=True
            )

        self.assertEqual(result, blob.public_url)
        self.assertEqual(blob.upload_args[1]["if_generation_match"], 0)
        self.assertTrue(blob.made_public)

    def test_storage_generation_conflict_returns_existing_image(self):
        db = FakeDB()
        blob = FakeBlob(fail_upload=True)
        bucket = type("Bucket", (), {"blob": lambda _self, _name: blob})()
        img = Image.new("RGB", (32, 32), "blue")
        data = io.BytesIO()
        img.save(data, format="JPEG")

        with patch.object(main, "get_db", return_value=db), \
             patch.object(main, "resolver_produto_id_com_sinonimo", side_effect=lambda _db, pid, *_args: pid), \
             patch.object(main.storage, "bucket", return_value=bucket), \
             patch.object(main.os, "makedirs", side_effect=OSError("skip local audit copy")):
            result = main.upload_imagem_cortada(
                data.getvalue(), [0, 0, 1000, 1000], "test", imagem_validada=True
            )

        self.assertEqual(result, blob.public_url)
        self.assertTrue(blob.reloaded)
        self.assertFalse(blob.made_public)

    def test_unvalidated_crop_is_not_uploaded(self):
        db = FakeDB()
        img = Image.new("RGB", (32, 32), "blue")
        data = io.BytesIO()
        img.save(data, format="JPEG")

        with patch.object(main, "get_db", return_value=db), \
             patch.object(main, "resolver_produto_id_com_sinonimo", side_effect=lambda _db, pid, *_args: pid), \
             patch.object(main.storage, "bucket") as bucket:
            result = main.upload_imagem_cortada(data.getvalue(), [0, 0, 1000, 1000], "test")

        self.assertEqual(result, "")
        bucket.assert_not_called()

    def test_same_price_offer_duplicates_are_collapsed_and_image_synced(self):
        now = datetime.now(timezone.utc)
        offer_data = {
            "produto_id": "arroz-x-un",
            "supermercado_id": "assai",
            "preco": 5.0,
            "expira_em": now + timedelta(days=2),
            "criado_em": now,
        }
        older_ref = FakeOfferRef(offer_data)
        latest_data = dict(offer_data, criado_em=now + timedelta(seconds=1))
        latest_ref = FakeOfferRef(latest_data)
        old_price_data = dict(offer_data, preco=4.5)
        old_price_ref = FakeOfferRef(old_price_data)
        docs = [
            FakeOfferSnapshot(older_ref, offer_data),
            FakeOfferSnapshot(latest_ref, latest_data),
            FakeOfferSnapshot(old_price_ref, old_price_data),
        ]
        db = FakeDB(
            {"imagem_url": "https://storage.googleapis.com/test-bucket/curada.jpg", "imagem_origem": "curadoria_manual"},
            docs,
        )

        with patch.object(main, "firestore") as firestore, \
             patch.object(main, "get_db", return_value=db), \
             patch.object(main, "resolver_produto_id_com_sinonimo", side_effect=lambda _db, pid, *_args: pid):
            firestore.client.return_value = db
            result = main.salvar_produto_e_oferta(
                nome="Arroz X", preco=5.0, unidade="un", categoria="ALIMENTOS",
                supermercado_id="assai", loja="Assaí", metodo="test", post_id="post-1"
            )

        self.assertTrue(result["duplicado"])
        self.assertTrue(older_ref.deleted)
        self.assertFalse(latest_ref.deleted)
        self.assertEqual(latest_ref.updates[-1]["imagem_url"], "https://storage.googleapis.com/test-bucket/curada.jpg")
        self.assertNotIn("preco", latest_ref.updates[-1])
        self.assertLess(old_price_ref.updates[-1]["expira_em"], datetime.now())

    def test_new_offer_expires_old_price_and_uses_daily_id_and_saved_image(self):
        old_data = {
            "produto_id": "arroz-x-un",
            "supermercado_id": "assai",
            "preco": 4.5,
            "expira_em": datetime.now(timezone.utc) + timedelta(days=1),
        }
        old_ref = FakeOfferRef(old_data)
        db = FakeDB(
            {"imagem_url": "https://storage.googleapis.com/test-bucket/curada.jpg", "imagem_origem": "curadoria_manual"},
            [FakeOfferSnapshot(old_ref, old_data)],
        )

        with patch.object(main, "firestore") as firestore, \
             patch.object(main, "get_db", return_value=db), \
             patch.object(main, "resolver_produto_id_com_sinonimo", side_effect=lambda _db, pid, *_args: pid):
            firestore.client.return_value = db
            result = main.salvar_produto_e_oferta(
                nome="Arroz X", preco=5.0, unidade="un", categoria="ALIMENTOS",
                supermercado_id="assai", loja="Assaí", metodo="test"
            )

        self.assertFalse(result["duplicado"])
        self.assertLess(old_ref.updates[-1]["expira_em"], datetime.now())
        expected_id = f"assai_arroz-x-un_{datetime.now().strftime('%Y-%m-%d')}"
        self.assertEqual(db.offer_collection._document_id, expected_id)
        saved_offer = db.offer_collection.docs_by_id[expected_id]
        self.assertEqual(saved_offer.sets[-1][0]["imagem_url"], "https://storage.googleapis.com/test-bucket/curada.jpg")


class ImageSearchFailClosedTests(unittest.TestCase):
    def test_missing_store_image_does_not_search_open_food_facts(self):
        with patch.object(main.session, "get") as get:
            self.assertEqual(main.buscar_imagem("Feijão Rosita 1kg"), "")
        get.assert_not_called()

    def test_explicit_store_image_is_returned_without_general_search(self):
        image_url = "https://cdn.supermarket.example/products/feijao-rosita-1kg.jpg"
        with patch.object(main.session, "get") as get:
            self.assertEqual(main.buscar_imagem("Feijão Rosita 1kg", image_url), image_url)
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
