import io
import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

if "anthropic" not in sys.modules:
    anthropic_stub = types.ModuleType("anthropic")
    anthropic_stub.Anthropic = type("Anthropic", (), {})
    sys.modules["anthropic"] = anthropic_stub

if "src.services.pdf_converter" not in sys.modules:
    pdf_converter_stub = types.ModuleType("src.services.pdf_converter")
    pdf_converter_stub.PdfConverter = type("PdfConverter", (), {})
    sys.modules["src.services.pdf_converter"] = pdf_converter_stub

from src.api.main import app
from src.api.schemas.documents import IncubatorNumber
from src.models.storage import Storage
from src.services.documents import DocumentService


class DocumentIngestionTests(unittest.TestCase):
    def test_incubator_numbers_are_exactly_one_to_eight(self) -> None:
        self.assertEqual(
            [member.value for member in IncubatorNumber], list(range(1, 9))
        )

    def test_upload_openapi_requires_incubator_selection(self) -> None:
        schema = app.openapi()
        body_ref = schema["paths"]["/documents"]["post"]["requestBody"]["content"][
            "multipart/form-data"
        ]["schema"]["$ref"]
        body_name = body_ref.rsplit("/", 1)[-1]
        upload_body = schema["components"]["schemas"][body_name]

        self.assertIn("incubator_number", upload_body["required"])
        self.assertEqual(
            schema["components"]["schemas"]["IncubatorNumber"]["enum"],
            list(range(1, 9)),
        )

    @patch("src.services.documents.DocumentRepo.crear")
    @patch("src.services.documents.Storage.guardar")
    @patch("src.services.documents.Storage.preparar_nombre")
    def test_upload_persists_selected_incubator(
        self,
        preparar_nombre: Mock,
        guardar: Mock,
        crear: Mock,
    ) -> None:
        preparar_nombre.return_value = (
            "documento.pdf",
            "pdf",
            "document-id",
            "document-id.pdf",
        )
        guardar.return_value = "s3/archivosCrudos/document-id.pdf"
        creado = SimpleNamespace(id="document-id", incubator_number=3)
        crear.return_value = creado
        archivo = SimpleNamespace(
            filename="documento.pdf",
            file=io.BytesIO(b"contenido"),
        )

        resultado = DocumentService.cargar_documento(Mock(), archivo, 3, None)

        self.assertIs(resultado, creado)
        self.assertEqual(crear.call_args.kwargs["incubator_number"], 3)

    def test_optional_storage_path_can_be_deleted(self) -> None:
        Storage.eliminar(None)
        Storage.eliminar_directorio(None)

    @patch("src.services.documents.DocumentRepo.eliminar")
    @patch("src.services.documents.Storage.eliminar_directorio")
    @patch("src.services.documents.Storage.eliminar")
    def test_document_deletion_includes_images_directory(
        self,
        eliminar: Mock,
        eliminar_directorio: Mock,
        eliminar_documento: Mock,
    ) -> None:
        db = Mock()
        documento = SimpleNamespace(
            file_path="s3/archivosCrudos/document-id.pdf",
            converted_path=None,
            cleaned_path=None,
            ner_path=None,
            images_path="s3/imagenesExtraidas/document-id",
        )

        DocumentService.eliminar(db, documento)

        eliminar_directorio.assert_called_once_with(documento.images_path)
        eliminar_documento.assert_called_once_with(db, documento)


if __name__ == "__main__":
    unittest.main()
