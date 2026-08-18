import os
import unittest
from unittest.mock import Mock
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from src.models.documents import Document  # noqa: F401
from src.models.entities_repo import EntityRepo


class EntityRepoTests(unittest.TestCase):
    def test_resolution_traceability_is_persisted_with_original_mention(self) -> None:
        db = Mock()
        document_id = uuid4()
        canonical_id = uuid4()
        details = {
            "preferred_name": "minero",
            "rule": "controlled_spanish_singularization",
        }

        EntityRepo.reemplazar_entidades(
            db,
            document_id,
            [
                {
                    "canonical_id": canonical_id,
                    "category": "CHAR",
                    "text": "MINEROS",
                    "start": 10,
                    "end": 17,
                    "sentence_id": "s-1",
                    "context": "Los MINEROS trabajan.",
                    "ambiguity": "low",
                    "match_type": "morphology",
                    "match_score": 100.0,
                    "resolution_version": "deterministic-v2",
                    "resolution_details": details,
                }
            ],
        )

        entity = db.add.call_args.args[0]
        self.assertEqual(entity.text, "MINEROS")
        self.assertEqual(entity.canonical_id, canonical_id)
        self.assertEqual(entity.resolution_method, "morphology")
        self.assertEqual(entity.resolution_score, 100.0)
        self.assertEqual(entity.resolution_version, "deterministic-v2")
        self.assertEqual(entity.resolution_details, details)
        db.flush.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
