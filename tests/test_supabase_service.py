from types import SimpleNamespace

from app.services.supabase_service import SupabaseService


class _FakeFilterBuilder:
    def __init__(self, table_name, outcomes):
        self._table_name = table_name
        self._outcomes = outcomes
        self._id = None

    def eq(self, column, value):
        assert column == "id"
        self._id = value
        return self

    def execute(self):
        outcome = self._outcomes.get((self._table_name, self._id), {})
        if outcome.get("raise"):
            raise outcome["raise"]
        count = outcome.get("count", 0)
        data = outcome.get("data", [])
        return SimpleNamespace(count=count, data=data)


class _FakeTableBuilder:
    def __init__(self, table_name, outcomes):
        self._table_name = table_name
        self._outcomes = outcomes

    def update(self, payload, count=None):
        assert "drive_folder_id" in payload
        assert count == "exact"
        return _FakeFilterBuilder(self._table_name, self._outcomes)


class _FakeSupabaseClient:
    def __init__(self, outcomes):
        self._outcomes = outcomes

    def table(self, table_name):
        return _FakeTableBuilder(table_name, self._outcomes)


def test_actualizar_drive_folder_ids_reporta_no_encontrado():
    service = SupabaseService(
        supabase_url="http://fake.local",
        supabase_key="header.payload.signature",
    )
    service.supabase = _FakeSupabaseClient(
        outcomes={
            ("fct_acreditacion_solicitud_trabajador_manual", 123): {"count": 0, "data": []},
        }
    )

    payload = {
        "myma": {
            "especialistas": [{"id": 123, "nombre": "Test", "id_folder": "folder-1"}],
            "conductores": [],
            "vehiculos": [],
        },
        "externo": {"empresa": "X", "especialistas": [], "conductores": [], "vehiculos": []},
    }

    result = service.actualizar_drive_folder_ids(payload)

    assert result["especialistas_myma"]["intentados"] == 1
    assert result["especialistas_myma"]["exitosos"] == 0
    assert result["especialistas_myma"]["no_encontrado"] == 1
    assert result["resumen"]["intentados"] == 1
    assert result["resumen"]["exitosos"] == 0


def test_actualizar_drive_folder_ids_omite_registro_sin_id_folder():
    service = SupabaseService(
        supabase_url="http://fake.local",
        supabase_key="header.payload.signature",
    )
    service.supabase = _FakeSupabaseClient(outcomes={})

    payload = {
        "myma": {
            "especialistas": [{"id": 123, "nombre": "Test"}],
            "conductores": [],
            "vehiculos": [],
        },
        "externo": {"empresa": "X", "especialistas": [], "conductores": [], "vehiculos": []},
    }

    result = service.actualizar_drive_folder_ids(payload)

    assert result["especialistas_myma"]["intentados"] == 0
    assert result["especialistas_myma"]["omitidos_sin_id_folder"] == 1
    assert result["resumen"]["omitidos_sin_id_folder"] == 1


def test_actualizar_drive_folder_ids_actualiza_vehiculo_myma_y_suma_resumen():
    service = SupabaseService(
        supabase_url="http://fake.local",
        supabase_key="header.payload.signature",
    )
    service.supabase = _FakeSupabaseClient(
        outcomes={
            ("fct_acreditacion_solicitud_vehiculos", 321): {"count": 1, "data": [{"id": 321}]},
        }
    )

    payload = {
        "myma": {
            "especialistas": [],
            "conductores": [],
            "vehiculos": [{"id": 321, "patente": "ZXCV99", "id_folder": "folder-v1"}],
        },
        "externo": {"empresa": "X", "especialistas": [], "conductores": [], "vehiculos": []},
    }

    result = service.actualizar_drive_folder_ids(payload)

    assert result["vehiculos_myma"]["intentados"] == 1
    assert result["vehiculos_myma"]["exitosos"] == 1
    assert result["resumen"]["intentados"] == 1
    assert result["resumen"]["exitosos"] == 1


def test_actualizar_drive_folder_ids_vehiculo_externo_reporta_no_encontrado():
    service = SupabaseService(
        supabase_url="http://fake.local",
        supabase_key="header.payload.signature",
    )
    service.supabase = _FakeSupabaseClient(
        outcomes={
            ("fct_acreditacion_solicitud_vehiculos", 555): {"count": 0, "data": []},
        }
    )

    payload = {
        "myma": {"especialistas": [], "conductores": [], "vehiculos": []},
        "externo": {
            "empresa": "X",
            "especialistas": [],
            "conductores": [],
            "vehiculos": [{"id": 555, "patente": "ZXCV88", "id_folder": "folder-v2"}],
        },
    }

    result = service.actualizar_drive_folder_ids(payload)

    assert result["vehiculos_externo"]["intentados"] == 1
    assert result["vehiculos_externo"]["exitosos"] == 0
    assert result["vehiculos_externo"]["no_encontrado"] == 1
    assert result["resumen"]["intentados"] == 1
    assert result["resumen"]["no_encontrado"] == 1


def test_actualizar_drive_folder_ids_vehiculo_omite_sin_id_folder():
    service = SupabaseService(
        supabase_url="http://fake.local",
        supabase_key="header.payload.signature",
    )
    service.supabase = _FakeSupabaseClient(outcomes={})

    payload = {
        "myma": {"especialistas": [], "conductores": [], "vehiculos": []},
        "externo": {
            "empresa": "X",
            "especialistas": [],
            "conductores": [],
            "vehiculos": [{"id": 777, "patente": "ZXCV77"}],
        },
    }

    result = service.actualizar_drive_folder_ids(payload)

    assert result["vehiculos_externo"]["intentados"] == 0
    assert result["vehiculos_externo"]["omitidos_sin_id_folder"] == 1
    assert result["resumen"]["omitidos_sin_id_folder"] == 1


def test_actualizar_drive_folder_ids_sin_configuracion():
    service = SupabaseService(
        supabase_url="http://fake.local",
        supabase_key="header.payload.signature",
    )
    service.supabase = None

    result = service.actualizar_drive_folder_ids({})

    assert result["estado"] == "sin_configuracion_supabase"
    assert "vehiculos_myma" in result
    assert "vehiculos_externo" in result
    assert result["resumen"]["intentados"] == 0
