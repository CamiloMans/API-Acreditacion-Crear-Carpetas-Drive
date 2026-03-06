"""Tests basicos para la API."""

from fastapi.testclient import TestClient

from app.main import app
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


def test_crear_carpetas_invalid_code():
    """Test del endpoint crear carpetas con codigo invalido."""
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
    assert response.status_code == 422  # Validation error


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
