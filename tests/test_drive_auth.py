"""Tests para autenticacion de Google Drive no interactiva."""

import pytest

from app.services import drive_service as drive_module
from app.services.drive_service import DriveService


class FakeCreds:
    """Credenciales simuladas para probar get_service."""

    def __init__(
        self,
        *,
        valid: bool,
        expired: bool,
        refresh_token: str | None,
        refresh_error: Exception | None = None,
    ):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refresh_error = refresh_error
        self.refresh_called = False

    def refresh(self, _request) -> None:
        self.refresh_called = True
        if self.refresh_error:
            raise self.refresh_error
        self.valid = True

    def to_json(self) -> str:
        return '{"access_token":"new-token"}'


def test_get_service_raises_when_token_file_missing(tmp_path):
    """Debe fallar rapido cuando no existe token.json."""
    service = DriveService(token_file=str(tmp_path / "missing_token.json"))

    with pytest.raises(RuntimeError, match="No se encontro el archivo de token"):
        service.get_service()


def test_get_service_raises_when_token_json_is_invalid(tmp_path):
    """Un archivo presente pero malformado debe producir un error claro."""
    token_path = tmp_path / "token.json"
    token_path.write_text("{invalid-json", encoding="utf-8")

    service = DriveService(token_file=str(token_path))

    with pytest.raises(RuntimeError, match="No se pudo cargar el token OAuth"):
        service.get_service()


def test_get_service_uses_valid_token_without_refresh(tmp_path, monkeypatch):
    """Cuando el token es valido, no debe refrescar."""
    token_path = tmp_path / "token.json"
    token_path.write_text('{"token":"ok"}', encoding="utf-8")

    fake_creds = FakeCreds(valid=True, expired=False, refresh_token="refresh")
    built_service = object()
    build_calls = {"count": 0}

    monkeypatch.setattr(
        drive_module.Credentials,
        "from_authorized_user_file",
        lambda _path, _scopes: fake_creds,
    )

    def fake_build(_name, _version, credentials):
        build_calls["count"] += 1
        assert credentials is fake_creds
        return built_service

    monkeypatch.setattr(drive_module, "build", fake_build)

    service = DriveService(token_file=str(token_path))
    result = service.get_service()

    assert result is built_service
    assert build_calls["count"] == 1
    assert not fake_creds.refresh_called


def test_get_service_refreshes_expired_token_and_persists(tmp_path, monkeypatch):
    """Si el token expira y hay refresh_token, debe refrescar y guardar."""
    token_path = tmp_path / "token.json"
    token_path.write_text('{"token":"expired"}', encoding="utf-8")

    fake_creds = FakeCreds(valid=False, expired=True, refresh_token="refresh")

    monkeypatch.setattr(
        drive_module.Credentials,
        "from_authorized_user_file",
        lambda _path, _scopes: fake_creds,
    )
    monkeypatch.setattr(drive_module, "build", lambda *_args, **_kwargs: {"ok": True})

    service = DriveService(token_file=str(token_path))
    result = service.get_service()

    assert result == {"ok": True}
    assert fake_creds.refresh_called
    assert token_path.read_text(encoding="utf-8") == fake_creds.to_json()


def test_get_service_continues_when_refreshed_token_is_read_only(
    tmp_path, monkeypatch, caplog
):
    """Render puede montar secretos de solo lectura; el refresh debe seguir en memoria."""
    token_path = tmp_path / "token.json"
    token_path.write_text('{"token":"expired"}', encoding="utf-8")
    fake_creds = FakeCreds(valid=False, expired=True, refresh_token="refresh")

    monkeypatch.setattr(
        drive_module.Credentials,
        "from_authorized_user_file",
        lambda _path, _scopes: fake_creds,
    )
    monkeypatch.setattr(drive_module, "build", lambda *_args, **_kwargs: {"ok": True})

    original_open = open

    def read_only_open(path, mode="r", *args, **kwargs):
        if str(path) == str(token_path) and "w" in mode:
            raise PermissionError("read-only secret")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", read_only_open)

    result = DriveService(token_file=str(token_path)).get_service()

    assert result == {"ok": True}
    assert fake_creds.refresh_called
    assert "refrescado en memoria" in caplog.text


def test_get_service_raises_when_refresh_fails(tmp_path, monkeypatch):
    """Un refresh OAuth rechazado sigue siendo un error fatal."""
    token_path = tmp_path / "token.json"
    token_path.write_text('{"token":"expired"}', encoding="utf-8")
    fake_creds = FakeCreds(
        valid=False,
        expired=True,
        refresh_token="refresh",
        refresh_error=RuntimeError("invalid_grant"),
    )
    monkeypatch.setattr(
        drive_module.Credentials,
        "from_authorized_user_file",
        lambda _path, _scopes: fake_creds,
    )

    with pytest.raises(RuntimeError, match="No se pudo refrescar el token OAuth"):
        DriveService(token_file=str(token_path)).get_service()


def test_get_service_raises_when_invalid_and_without_refresh_token(tmp_path, monkeypatch):
    """No debe intentar fallback interactivo si no existe refresh_token."""
    token_path = tmp_path / "token.json"
    token_path.write_text('{"token":"invalid"}', encoding="utf-8")

    fake_creds = FakeCreds(valid=False, expired=True, refresh_token=None)
    monkeypatch.setattr(
        drive_module.Credentials,
        "from_authorized_user_file",
        lambda _path, _scopes: fake_creds,
    )

    service = DriveService(token_file=str(token_path))

    with pytest.raises(RuntimeError, match="sin refresh_token"):
        service.get_service()
