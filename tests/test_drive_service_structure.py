from app.services.drive_service import DriveService


class InMemoryDriveService(DriveService):
    """DriveService doble para tests sin llamadas a Google API."""

    def __init__(self):
        super().__init__(token_file="unused-token.json")
        self._counter = 0
        self.shared_drives = {}
        self.children = {}

    def _new_id(self) -> str:
        self._counter += 1
        return f"id-{self._counter}"

    def add_shared_drive(self, name: str, drive_id: str) -> None:
        self.shared_drives[name] = drive_id
        self.children.setdefault(drive_id, [])

    def add_folder(self, parent_id: str, name: str, folder_id: str | None = None) -> str:
        folder_id = folder_id or self._new_id()
        self.children.setdefault(parent_id, []).append((name, folder_id))
        self.children.setdefault(folder_id, [])
        return folder_id

    def find_shared_drive_by_name(self, drive_name: str):
        for existing_name, drive_id in self.shared_drives.items():
            if self._match_folder_name(existing_name, drive_name):
                return drive_id
        return None

    def list_folders_in_directory(self, parent_id, drive_id=None, max_results=1000):
        return list(self.children.get(parent_id, []))[:max_results]

    def create_folder(self, name, parent_id, drive_id=None):
        return self.add_folder(parent_id, name)


def _names_under(service: InMemoryDriveService, parent_id: str) -> list[str]:
    return [name for name, _ in service.list_folders_in_directory(parent_id)]


def test_procesar_codigo_proyecto_falla_si_no_existe_shared_drive():
    service = InMemoryDriveService()

    result = service.procesar_codigo_proyecto({"codigo_proyecto": "MY-001-2026"})

    assert result is None


def test_procesar_codigo_proyecto_falla_si_no_existe_carpeta_base_acreditaciones():
    service = InMemoryDriveService()
    service.add_shared_drive("Acreditaciones", "drive-1")

    result = service.procesar_codigo_proyecto({"codigo_proyecto": "MY-001-2026"})

    assert result is None


def test_procesar_codigo_proyecto_crea_proyectos_y_codigo_si_faltan():
    service = InMemoryDriveService()
    service.add_shared_drive("Acreditaciones", "drive-1")
    carpeta_acreditaciones_id = service.add_folder("drive-1", "Acreditaciones")

    result = service.procesar_codigo_proyecto({"codigo_proyecto": "MY-001-2026"})

    assert result is not None
    assert result["nombre_drive"] == "Acreditaciones"
    assert result["a\u00f1o_proyecto"] == "2026"
    assert result["carpeta_acreditaciones_id"] == carpeta_acreditaciones_id

    carpeta_proyectos_id = service.find_folder_by_name_in_directory(
        "Proyectos 2026", carpeta_acreditaciones_id, "drive-1"
    )
    assert carpeta_proyectos_id is not None

    carpeta_codigo_id = service.find_folder_by_name_in_directory(
        "MY-001-2026", carpeta_proyectos_id, "drive-1"
    )
    assert carpeta_codigo_id is not None
    assert result["id_carpeta_proyecto"] == carpeta_codigo_id


def test_navegar_ruta_proyecto_devuelve_carpeta_final_nueva_ruta():
    service = InMemoryDriveService()
    service.add_shared_drive("Acreditaciones", "drive-1")
    carpeta_acreditaciones_id = service.add_folder("drive-1", "Acreditaciones")
    carpeta_proyectos_id = service.add_folder(carpeta_acreditaciones_id, "Proyectos 2026")
    carpeta_codigo_id = service.add_folder(carpeta_proyectos_id, "MY-001-2026")

    result = service.navegar_ruta_proyecto("MY-001-2026", "drive-1")

    assert result is not None
    assert result["id_carpeta_final"] == carpeta_codigo_id
    assert [nivel["nombre"] for nivel in result["niveles"]] == [
        "Acreditaciones",
        "Proyectos 2026",
        "MY-001-2026",
    ]


def test_find_folder_by_name_ignora_mayusculas_y_tildes():
    service = InMemoryDriveService()
    service.add_shared_drive("Acreditaciones", "drive-1")
    parent_id = service.add_folder("drive-1", "Acreditaciones")
    carpeta_id = service.add_folder(parent_id, "Acreditaci\u00f3n")

    result = service.find_folder_by_name_in_directory("acreditacion", parent_id, "drive-1")

    assert result == carpeta_id


def test_find_folder_by_name_ignora_prefijo_numerico_solo_cuando_corresponde():
    service = InMemoryDriveService()
    service.add_shared_drive("Acreditaciones", "drive-1")
    parent_id = service.add_folder("drive-1", "Acreditaciones")
    carpeta_id = service.add_folder(parent_id, "01 Empresa")

    result_match = service.find_folder_by_name_in_directory(
        "Empresa",
        parent_id,
        "drive-1",
        ignore_numeric_prefix=True,
    )
    result_no_match = service.find_folder_by_name_in_directory(
        "Empresa",
        parent_id,
        "drive-1",
        ignore_numeric_prefix=False,
    )

    assert result_match == carpeta_id
    assert result_no_match is None


def test_gestionar_carpetas_externos_crea_estructura_contratista_y_subcarpetas():
    service = InMemoryDriveService()
    service.add_shared_drive("Acreditaciones", "drive-1")
    carpeta_proyecto_id = service.add_folder("drive-1", "MY-001-2026")

    payload = {
        "empresa": "AGQ",
        "especialistas": [{"id": 1, "nombre": "Ana"}],
        "conductores": [{"id": 2, "nombre": "Carlos"}],
        "vehiculos": [{"id": 3, "patente": "ABCD11"}],
    }

    result = service.gestionar_carpetas_externos(carpeta_proyecto_id, payload, "drive-1")

    carpeta_externos_id = result["carpeta_externos_id"]
    carpeta_empresa_id = result["carpeta_empresa_id"]

    assert "Externos" in _names_under(service, carpeta_proyecto_id)
    assert "AGQ" in _names_under(service, carpeta_externos_id)

    nombres_base = _names_under(service, carpeta_empresa_id)
    assert "01 Empresa" in nombres_base
    assert "02 Especialistas" in nombres_base
    assert "03 Conductores" in nombres_base
    assert "04 Vehiculos" in nombres_base

    carpeta_especialistas_id = result["carpetas_creadas"]["02 Especialistas"]
    carpeta_conductores_id = result["carpetas_creadas"]["03 Conductores"]
    carpeta_vehiculos_id = result["carpetas_creadas"]["04 Vehiculos"]

    assert "Ana" in _names_under(service, carpeta_especialistas_id)
    assert "Carlos" in _names_under(service, carpeta_conductores_id)
    assert "ABCD11" in _names_under(service, carpeta_vehiculos_id)


def test_gestionar_carpetas_myma_crea_estructura_y_subcarpetas():
    service = InMemoryDriveService()
    service.add_shared_drive("Acreditaciones", "drive-1")
    carpeta_proyecto_id = service.add_folder("drive-1", "MY-001-2026")

    payload = {
        "especialistas": [{"id": 10, "nombre": "Luis"}],
        "conductores": [{"id": 11, "nombre": "Marta"}],
        "vehiculos": [{"id": 12, "patente": "ZXCV99"}],
    }

    result = service.gestionar_carpetas_myma(carpeta_proyecto_id, payload, "drive-1")

    carpeta_myma_id = result["carpeta_myma_id"]
    assert "MYMA" in _names_under(service, carpeta_proyecto_id)

    nombres_base = _names_under(service, carpeta_myma_id)
    assert "01 Empresa" in nombres_base
    assert "02 Especialistas" in nombres_base
    assert "03 Conductores" in nombres_base
    assert "04 Vehiculos" in nombres_base

    carpeta_especialistas_id = result["carpetas_creadas"]["02 Especialistas"]
    carpeta_conductores_id = result["carpetas_creadas"]["03 Conductores"]
    carpeta_vehiculos_id = result["carpetas_creadas"]["04 Vehiculos"]

    assert "Luis" in _names_under(service, carpeta_especialistas_id)
    assert "Marta" in _names_under(service, carpeta_conductores_id)
    assert "ZXCV99" in _names_under(service, carpeta_vehiculos_id)

