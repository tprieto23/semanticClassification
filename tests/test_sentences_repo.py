import os
import unittest
from unittest.mock import Mock
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from src.models.sentences_repo import SentenceRepo


class SentenceRepoTests(unittest.TestCase):
    def test_reemplazar_por_documento_borra_previas_y_agrega_nuevas(self) -> None:
        db = Mock()
        document_id = uuid4()

        SentenceRepo.reemplazar_por_documento(
            db,
            document_id,
            [
                {"sentence_id": "s-1", "text": "Los mineros trabajan."},
                {"sentence_id": "s-2", "text": "La comunidad observa."},
            ],
        )

        db.query.return_value.filter.return_value.delete.assert_called_once_with()
        self.assertEqual(db.add.call_count, 2)

        first = db.add.call_args_list[0].args[0]
        second = db.add.call_args_list[1].args[0]
        self.assertEqual(first.document_id, document_id)
        self.assertEqual(first.sentence_id, "s-1")
        self.assertEqual(first.text, "Los mineros trabajan.")
        self.assertEqual(second.sentence_id, "s-2")
        self.assertEqual(second.text, "La comunidad observa.")

    def test_eliminar_por_documento(self) -> None:
        db = Mock()
        document_id = uuid4()

        SentenceRepo.eliminar_por_documento(db, document_id)

        db.query.return_value.filter.return_value.delete.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
