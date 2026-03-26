"""Tests basicos para la API."""

from fastapi.testclient import TestClient

from app.main import app
from app.routers.carpetas import get_drive_service, get_supabase_service
from app.services.drive_service import DriveService

client = TestClient(app)


def test_root():
    """Test del endpoint raiz."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["status"] == "running"


def test_health():
    """Test del endpoint de health."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_crear_carpetas_invalid_code_usa_fallback_contrato_marco():
    """Codigo invalido para MY debe seguir flujo exitoso por Contrato Marco."""

    class FakeDriveService:
        def procesar_codigo_proyecto(self, _proyecto):
            return {
                "codigo_proyecto": "INVALID-CODE",
                "codigo_proyecto_saneado": "INVALID-CODE",
                "ruta_tipo": "contrato_marco",
                "a\u00f1o_proyecto": "",
                "nombre_drive": "Acreditaciones",
                "drive_id": "drive-1",
            }

        def navegar_ruta_proyecto(self, _codigo_proyecto, _drive_id):
            return {"id_carpeta_final": "folder-1"}

        def gestionar_carpetas_externos(self, _id_carpeta, _externo, _drive_id):
            return {"subcarpetas_creadas": {}}

        def gestionar_carpetas_myma(self, _id_carpeta, _myma, _drive_id):
            return {"subcarpetas_creadas": {}}

        def generar_json_final(self, proyecto, _externos, _myma):
            return proyecto

    class FakeSupabaseService:
        def actualizar_drive_folder_ids(self, _json_final):
            return {"resumen": {"intentados": 0, "exitosos": 0}}

    app.dependency_overrides[get_drive_service] = lambda: FakeDriveService()
    app.dependency_overrides[get_supabase_service] = lambda: FakeSupabaseService()

    try:
        response = client.post(
            "/carpetas/crear",
            json={
                "codigo_proyecto": "INVALID-CODE",
                "myma": {
                    "especialistas": [],
                    "conductores": [],
                    "vehiculos": [],
                },
                "externo": {
                    "empresa": "Test",
                    "especialistas": [],
                    "conductores": [],
                    "vehiculos": [],
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["a\u00f1o_proyecto"] == ""
    assert response.json()["id_carpeta_final"] == "folder-1"


def test_crear_carpetas_missing_fields():
    """Test del endpoint crear carpetas con campos faltantes."""
    response = client.post(
        "/carpetas/crear",
        json={
            "codigo_proyecto": "MY-000-2026",
        },
    )
    assert response.status_code == 422  # Validation error


def test_crear_carpetas_drive_auth_error(monkeypatch):
    """Si falla auth de Drive, la API debe retornar error interno."""

    def raise_auth_error(_self):
        raise RuntimeError("Token invalido para Google Drive")

    monkeypatch.setattr(DriveService, "get_service", raise_auth_error)

    response = client.post(
        "/carpetas/crear",
        json={
            "codigo_proyecto": "MY-000-2026",
            "myma": {
                "especialistas": [],
                "conductores": [],
                "vehiculos": [],
            },
            "externo": {
                "empresa": "Test",
                "especialistas": [],
                "conductores": [],
                "vehiculos": [],
            },
        },
    )

    assert response.status_code == 500
    assert "Token invalido para Google Drive" in response.json()["detail"]


def test_crear_carpetas_acepta_empresa_externa_null(monkeypatch):
    """empresa null en externo no debe fallar validacion Pydantic."""

    def raise_auth_error(_self):
        raise RuntimeError("Token invalido para Google Drive")

    monkeypatch.setattr(DriveService, "get_service", raise_auth_error)

    response = client.post(
        "/carpetas/crear",
        json={
            "codigo_proyecto": "MY-000-2026",
            "myma": {
                "especialistas": [],
                "conductores": [],
                "vehiculos": [],
            },
            "externo": {
                "empresa": None,
                "especialistas": [],
                "conductores": [],
                "vehiculos": [],
            },
        },
    )

    assert response.status_code == 500
    assert "Token invalido para Google Drive" in response.json()["detail"]
