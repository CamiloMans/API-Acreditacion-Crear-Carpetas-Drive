"""Servicio para interactuar con Google Drive API."""
import json
import logging
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings
from app.utils.helpers import obtener_id_elemento, obtener_nombre_elemento

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]

ACREDITACIONES_DRIVE_NAME = "Acreditaciones"
ACREDITACIONES_ROOT_FOLDER_NAME = "Acreditaciones"
EXTERNOS_FOLDER_NAME = "Externos"
MYMA_FOLDER_NAME = "MYMA"
BASE_FOLDER_LABELS = {
    "empresa": "01 Empresa",
    "especialistas": "02 Especialistas",
    "conductores": "03 Conductores",
    "vehiculos": "04 Vehiculos",
}
NUMERIC_PREFIX_PATTERN = re.compile(r"^\s*\d+\s*[-_.]?\s*")


class DriveService:
    """Servicio para interactuar con Google Drive API."""

    def __init__(self, token_file: Optional[str] = None):
        self.token_file = token_file or settings.google_token_file
        self.service = None

    @staticmethod
    def _normalize_name(value: str) -> str:
        """Normaliza texto para comparacion exacta sin mayusculas ni tildes."""
        normalized = unicodedata.normalize("NFD", value or "")
        without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        collapsed_spaces = " ".join(without_accents.strip().split())
        return collapsed_spaces.casefold()

    def _normalize_base_folder_label(self, value: str) -> str:
        """Normaliza etiquetas base ignorando prefijo numerico (01, 02, ...)."""
        normalized = self._normalize_name(value)
        return NUMERIC_PREFIX_PATTERN.sub("", normalized)

    def _match_folder_name(self, actual_name: str, expected_name: str, ignore_numeric_prefix: bool = False) -> bool:
        """Compara nombres de carpeta con reglas de normalizacion definidas."""
        if ignore_numeric_prefix:
            return self._normalize_base_folder_label(actual_name) == self._normalize_base_folder_label(expected_name)
        return self._normalize_name(actual_name) == self._normalize_name(expected_name)

    def _find_or_create_folder(
        self,
        folder_name: str,
        parent_id: str,
        drive_id: Optional[str] = None,
        ignore_numeric_prefix: bool = False,
    ) -> str:
        """Busca carpeta por nombre o la crea si no existe."""
        folder_id = self.find_folder_by_name_in_directory(
            folder_name=folder_name,
            parent_id=parent_id,
            drive_id=drive_id,
            ignore_numeric_prefix=ignore_numeric_prefix,
        )
        if folder_id:
            return folder_id
        return self.create_folder(folder_name, parent_id, drive_id)

    def _resolver_estructura_proyecto(
        self,
        codigo_proyecto: str,
        drive_id: str,
        crear_proyectos_anio: bool,
        crear_carpeta_proyecto: bool,
    ) -> Optional[Dict[str, Any]]:
        """Resuelve/c crea la ruta Acreditaciones/Acreditaciones/Proyectos YYYY/codigo."""
        match = re.match(r"^MY-\d{3}-(\d{4})$", codigo_proyecto)
        if not match:
            logger.error(f"El codigo '{codigo_proyecto}' no tiene el formato correcto.")
            return None

        anio_proyecto = match.group(1)
        nombre_proyectos_anio = f"Proyectos {anio_proyecto}"

        carpeta_acreditaciones_id = self.find_folder_by_name_in_directory(
            ACREDITACIONES_ROOT_FOLDER_NAME,
            drive_id,
            drive_id,
        )
        if not carpeta_acreditaciones_id:
            logger.error(
                "No se encontro la carpeta base 'Acreditaciones' dentro del Shared Drive 'Acreditaciones'."
            )
            return None

        carpeta_proyectos_anio_id = self.find_folder_by_name_in_directory(
            nombre_proyectos_anio,
            carpeta_acreditaciones_id,
            drive_id,
        )
        if not carpeta_proyectos_anio_id:
            if not crear_proyectos_anio:
                logger.error(
                    f"No se encontro la carpeta '{nombre_proyectos_anio}' y no esta permitido crearla."
                )
                return None
            carpeta_proyectos_anio_id = self.create_folder(
                nombre_proyectos_anio,
                carpeta_acreditaciones_id,
                drive_id,
            )

        carpeta_proyecto_id = self.find_folder_by_name_in_directory(
            codigo_proyecto,
            carpeta_proyectos_anio_id,
            drive_id,
        )
        if not carpeta_proyecto_id:
            if not crear_carpeta_proyecto:
                logger.error(
                    f"No se encontro la carpeta del proyecto '{codigo_proyecto}' y no esta permitido crearla."
                )
                return None
            carpeta_proyecto_id = self.create_folder(codigo_proyecto, carpeta_proyectos_anio_id, drive_id)

        return {
            "anio_proyecto": anio_proyecto,
            "nombre_proyectos_anio": nombre_proyectos_anio,
            "carpeta_acreditaciones_id": carpeta_acreditaciones_id,
            "carpeta_proyectos_anio_id": carpeta_proyectos_anio_id,
            "carpeta_proyecto_id": carpeta_proyecto_id,
        }

    def _crear_subcarpetas_registros(
        self,
        registros: List[Dict[str, Any]],
        parent_id: Optional[str],
        drive_id: str,
        field_name: str,
    ) -> List[Dict[str, Any]]:
        """Crea/reutiliza carpetas para cada registro y retorna metadata."""
        if not parent_id:
            return []

        resultado = []
        for elemento in registros or []:
            nombre = obtener_nombre_elemento(elemento)
            registro_id = obtener_id_elemento(elemento)

            folder_id = self.find_folder_by_name_in_directory(nombre, parent_id, drive_id)
            if not folder_id:
                folder_id = self.create_folder(nombre, parent_id, drive_id)

            item = {field_name: nombre, "carpeta_id": folder_id}
            if registro_id is not None:
                item["id"] = registro_id
            resultado.append(item)

        return resultado

    def get_service(self):
        """Construye y devuelve el cliente de Google Drive API v3 autenticado."""
        if self.service:
            return self.service

        if not os.path.exists(self.token_file):
            error_msg = (
                f"No se encontro el archivo de token en '{self.token_file}'. "
                "Configura GOOGLE_TOKEN_FILE con un token OAuth valido para produccion."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        except Exception as exc:
            error_msg = (
                f"No se pudo cargar el token OAuth desde '{self.token_file}'. "
                "Verifica formato JSON y permisos del archivo."
            )
            logger.error(f"{error_msg} Error: {exc}")
            raise RuntimeError(error_msg) from exc

        if not creds or not creds.valid:
            if creds and creds.refresh_token:
                logger.info("Token invalido detectado. Intentando refresh OAuth.")
                try:
                    creds.refresh(Request())
                except Exception as exc:
                    error_msg = (
                        "No se pudo refrescar el token OAuth. "
                        "Regenera token.json con refresh_token valido."
                    )
                    logger.error(f"{error_msg} Error: {exc}")
                    raise RuntimeError(error_msg) from exc

                try:
                    with open(self.token_file, "w", encoding="utf-8") as token:
                        token.write(creds.to_json())
                except Exception as exc:
                    error_msg = (
                        f"Token refrescado, pero no se pudo persistir en '{self.token_file}'. "
                        "Verifica permisos de escritura."
                    )
                    logger.error(f"{error_msg} Error: {exc}")
                    raise RuntimeError(error_msg) from exc
            else:
                error_msg = (
                    "Credenciales OAuth invalidas o sin refresh_token. "
                    "No hay fallback interactivo habilitado en produccion."
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)

        if not creds.valid:
            error_msg = "Las credenciales OAuth siguen invalidas despues del refresh."
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            self.service = build("drive", "v3", credentials=creds)
        except Exception as exc:
            error_msg = "No se pudo inicializar el cliente de Google Drive API."
            logger.error(f"{error_msg} Error: {exc}")
            raise RuntimeError(error_msg) from exc

        return self.service

    def find_shared_drive_by_name(self, drive_name: str) -> Optional[str]:
        """Busca un Shared Drive por nombre y retorna su ID."""
        service = self.get_service()
        page_token = None

        while True:
            try:
                results = service.drives().list(pageSize=100, pageToken=page_token).execute()

                drives = results.get("drives", [])
                for drive in drives:
                    if self._match_folder_name(drive.get("name", ""), drive_name):
                        return drive["id"]

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

            except Exception as e:
                logger.error(f"Error buscando Shared Drive: {e}")
                break

        return None

    def list_folders_in_directory(
        self,
        parent_id: str,
        drive_id: Optional[str] = None,
        max_results: int = 1000,
    ) -> List[Tuple[str, str]]:
        """Lista todas las carpetas dentro de un directorio especifico."""
        service = self.get_service()
        folders = []
        page_token = None

        if drive_id and parent_id == drive_id:
            query = (
                "mimeType = 'application/vnd.google-apps.folder' "
                f"and '{drive_id}' in parents and trashed = false"
            )
        else:
            query = (
                "mimeType = 'application/vnd.google-apps.folder' "
                f"and '{parent_id}' in parents and trashed = false"
            )

        while True:
            try:
                params = {
                    "q": query,
                    "spaces": "drive",
                    "fields": "nextPageToken, files(id, name, parents)",
                    "pageToken": page_token,
                    "pageSize": 100,
                    "orderBy": "name",
                    "supportsAllDrives": True,
                    "includeItemsFromAllDrives": True,
                }

                if drive_id:
                    params["driveId"] = drive_id
                    params["corpora"] = "drive"

                results = service.files().list(**params).execute()

                files = results.get("files", [])
                for file in files:
                    folders.append((file["name"], file["id"]))
                    if len(folders) >= max_results:
                        return folders

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

            except Exception as e:
                logger.error(f"Error listando carpetas: {e}")
                break

        return folders

    def find_folder_by_name_in_directory(
        self,
        folder_name: str,
        parent_id: str,
        drive_id: Optional[str] = None,
        ignore_numeric_prefix: bool = False,
    ) -> Optional[str]:
        """Busca carpeta por nombre exacto usando normalizacion configurable."""
        folders = self.list_folders_in_directory(parent_id, drive_id)

        for existing_name, folder_id in folders:
            if self._match_folder_name(existing_name, folder_name, ignore_numeric_prefix=ignore_numeric_prefix):
                return folder_id

        return None

    def find_folder_containing_name(
        self,
        folder_name_part: str,
        parent_id: str,
        drive_id: Optional[str] = None,
    ) -> Optional[str]:
        """Busca una carpeta que contenga un texto especifico en su nombre."""
        carpetas = self.list_folders_in_directory(parent_id, drive_id)
        target = self._normalize_name(folder_name_part)

        for nombre, carpeta_id in carpetas:
            if target in self._normalize_name(nombre):
                return carpeta_id

        return None

    def create_folder(self, name: str, parent_id: str, drive_id: Optional[str] = None) -> str:
        """Crea una carpeta dentro de parent_id y retorna el folderId creado."""
        service = self.get_service()
        body = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }

        if parent_id and not (drive_id and parent_id == drive_id):
            body["parents"] = [parent_id]

        create_params = {
            "body": body,
            "fields": "id",
            "supportsAllDrives": True,
        }

        if drive_id and parent_id == drive_id:
            create_params["driveId"] = drive_id

        folder = service.files().create(**create_params).execute()
        return folder["id"]

    def procesar_codigo_proyecto(self, datos_proyecto: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Procesa codigo y asegura ruta base del proyecto en Acreditaciones."""
        if isinstance(datos_proyecto, str):
            codigo_proyecto = datos_proyecto
            datos_completos = None
        elif isinstance(datos_proyecto, dict):
            if "codigo_proyecto" not in datos_proyecto:
                logger.error("El diccionario debe contener 'codigo_proyecto'")
                return None
            codigo_proyecto = datos_proyecto["codigo_proyecto"]
            datos_completos = datos_proyecto
        else:
            logger.error("datos_proyecto debe ser un diccionario o un string")
            return None

        patron = r"^MY-\d{3}-(\d{4})$"
        match = re.match(patron, codigo_proyecto)

        if not match:
            logger.error(f"El codigo '{codigo_proyecto}' no tiene el formato correcto.")
            return None

        anio_proyecto = match.group(1)
        nombre_proyectos_anio = f"Proyectos {anio_proyecto}"

        drive_id = self.find_shared_drive_by_name(ACREDITACIONES_DRIVE_NAME)
        if not drive_id:
            logger.error(f"No se encontro el Shared Drive '{ACREDITACIONES_DRIVE_NAME}'")
            return None

        estructura = self._resolver_estructura_proyecto(
            codigo_proyecto=codigo_proyecto,
            drive_id=drive_id,
            crear_proyectos_anio=True,
            crear_carpeta_proyecto=True,
        )
        if not estructura:
            return None

        resultado = {
            "codigo_proyecto": codigo_proyecto,
            "a\u00f1o_proyecto": anio_proyecto,
            "nombre_drive": ACREDITACIONES_DRIVE_NAME,
            "drive_id": drive_id,
            "carpeta_acreditaciones_id": estructura["carpeta_acreditaciones_id"],
            "carpeta_proyectos_anio_id": estructura["carpeta_proyectos_anio_id"],
            "id_carpeta_proyecto": estructura["carpeta_proyecto_id"],
            "nombre_carpeta_proyectos_anio": nombre_proyectos_anio,
            "carpetas": self.list_folders_in_directory(estructura["carpeta_proyectos_anio_id"], drive_id),
        }

        if datos_completos:
            resultado["datos_completos"] = datos_completos

        return resultado

    def navegar_ruta_proyecto(
        self,
        codigo_proyecto: str,
        drive_id: str,
        ruta_fija: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Navega la nueva ruta central y retorna la carpeta final del proyecto."""
        _ = ruta_fija  # Parametro mantenido por compatibilidad.

        estructura = self._resolver_estructura_proyecto(
            codigo_proyecto=codigo_proyecto,
            drive_id=drive_id,
            crear_proyectos_anio=True,
            crear_carpeta_proyecto=True,
        )
        if not estructura:
            return None

        niveles = [
            {
                "nombre": ACREDITACIONES_ROOT_FOLDER_NAME,
                "id": estructura["carpeta_acreditaciones_id"],
                "parent_id": drive_id,
                "nivel": 1,
            },
            {
                "nombre": estructura["nombre_proyectos_anio"],
                "id": estructura["carpeta_proyectos_anio_id"],
                "parent_id": estructura["carpeta_acreditaciones_id"],
                "nivel": 2,
            },
            {
                "nombre": codigo_proyecto,
                "id": estructura["carpeta_proyecto_id"],
                "parent_id": estructura["carpeta_proyectos_anio_id"],
                "nivel": 3,
            },
        ]

        return {
            "codigo_proyecto": codigo_proyecto,
            "carpeta_proyecto_id": estructura["carpeta_proyecto_id"],
            "niveles": niveles,
            "id_carpeta_final": estructura["carpeta_proyecto_id"],
        }

    def gestionar_carpetas_externos(
        self,
        id_carpeta_acreditacion: str,
        datos_externos: Dict[str, Any],
        drive_id: str,
    ) -> Dict[str, Any]:
        """Gestiona estructura Externos/<empresa>/01..04 y sus subcarpetas."""
        carpeta_externos_id = self._find_or_create_folder(
            EXTERNOS_FOLDER_NAME,
            id_carpeta_acreditacion,
            drive_id,
        )

        if not datos_externos or "empresa" not in datos_externos or not datos_externos["empresa"]:
            return {
                "carpeta_externos_id": carpeta_externos_id,
                "carpeta_empresa_id": None,
                "carpetas_creadas": {},
                "subcarpetas_creadas": {},
            }

        empresa_nombre = str(datos_externos["empresa"]).strip()
        carpeta_empresa_id = self._find_or_create_folder(empresa_nombre, carpeta_externos_id, drive_id)

        carpetas_creadas = {
            BASE_FOLDER_LABELS["empresa"]: self._find_or_create_folder(
                BASE_FOLDER_LABELS["empresa"],
                carpeta_empresa_id,
                drive_id,
                ignore_numeric_prefix=True,
            ),
            BASE_FOLDER_LABELS["especialistas"]: self._find_or_create_folder(
                BASE_FOLDER_LABELS["especialistas"],
                carpeta_empresa_id,
                drive_id,
                ignore_numeric_prefix=True,
            ),
            BASE_FOLDER_LABELS["conductores"]: self._find_or_create_folder(
                BASE_FOLDER_LABELS["conductores"],
                carpeta_empresa_id,
                drive_id,
                ignore_numeric_prefix=True,
            ),
            BASE_FOLDER_LABELS["vehiculos"]: self._find_or_create_folder(
                BASE_FOLDER_LABELS["vehiculos"],
                carpeta_empresa_id,
                drive_id,
                ignore_numeric_prefix=True,
            ),
        }

        subcarpetas_creadas = {
            "especialistas": self._crear_subcarpetas_registros(
                datos_externos.get("especialistas", []),
                carpetas_creadas[BASE_FOLDER_LABELS["especialistas"]],
                drive_id,
                "nombre",
            ),
            "conductores": self._crear_subcarpetas_registros(
                datos_externos.get("conductores", []),
                carpetas_creadas[BASE_FOLDER_LABELS["conductores"]],
                drive_id,
                "nombre",
            ),
            "vehiculos": self._crear_subcarpetas_registros(
                datos_externos.get("vehiculos", []),
                carpetas_creadas[BASE_FOLDER_LABELS["vehiculos"]],
                drive_id,
                "patente",
            ),
        }

        return {
            "carpeta_externos_id": carpeta_externos_id,
            "carpeta_empresa_id": carpeta_empresa_id,
            "carpetas_creadas": carpetas_creadas,
            "subcarpetas_creadas": subcarpetas_creadas,
        }

    def gestionar_carpetas_myma(
        self,
        id_carpeta_acreditacion: str,
        datos_myma: Dict[str, Any],
        drive_id: str,
    ) -> Dict[str, Any]:
        """Gestiona estructura MYMA/01..04 y subcarpetas por registros."""
        carpeta_myma_id = self._find_or_create_folder(MYMA_FOLDER_NAME, id_carpeta_acreditacion, drive_id)

        carpetas_creadas = {
            BASE_FOLDER_LABELS["empresa"]: self._find_or_create_folder(
                BASE_FOLDER_LABELS["empresa"],
                carpeta_myma_id,
                drive_id,
                ignore_numeric_prefix=True,
            ),
            BASE_FOLDER_LABELS["especialistas"]: self._find_or_create_folder(
                BASE_FOLDER_LABELS["especialistas"],
                carpeta_myma_id,
                drive_id,
                ignore_numeric_prefix=True,
            ),
            BASE_FOLDER_LABELS["conductores"]: self._find_or_create_folder(
                BASE_FOLDER_LABELS["conductores"],
                carpeta_myma_id,
                drive_id,
                ignore_numeric_prefix=True,
            ),
            BASE_FOLDER_LABELS["vehiculos"]: self._find_or_create_folder(
                BASE_FOLDER_LABELS["vehiculos"],
                carpeta_myma_id,
                drive_id,
                ignore_numeric_prefix=True,
            ),
        }

        subcarpetas_creadas = {
            "especialistas": self._crear_subcarpetas_registros(
                datos_myma.get("especialistas", []),
                carpetas_creadas[BASE_FOLDER_LABELS["especialistas"]],
                drive_id,
                "nombre",
            ),
            "conductores": self._crear_subcarpetas_registros(
                datos_myma.get("conductores", []),
                carpetas_creadas[BASE_FOLDER_LABELS["conductores"]],
                drive_id,
                "nombre",
            ),
            "vehiculos": self._crear_subcarpetas_registros(
                datos_myma.get("vehiculos", []),
                carpetas_creadas[BASE_FOLDER_LABELS["vehiculos"]],
                drive_id,
                "patente",
            ),
        }

        return {
            "carpeta_myma_id": carpeta_myma_id,
            "carpetas_creadas": carpetas_creadas,
            "subcarpetas_creadas": subcarpetas_creadas,
        }

    def generar_json_final(
        self,
        datos_proyecto: Dict[str, Any],
        resultado_carpetas_externos: Optional[Dict[str, Any]] = None,
        resultado_carpetas_myma: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Genera el JSON final con el id_folder de cada registro."""
        json_final = json.loads(json.dumps(datos_proyecto))

        # Agregar id_folder a los datos externos
        if resultado_carpetas_externos and "subcarpetas_creadas" in resultado_carpetas_externos:
            subcarpetas_externos = resultado_carpetas_externos["subcarpetas_creadas"]

            # Mapear especialistas
            if (
                "especialistas" in subcarpetas_externos
                and "externo" in json_final
                and "especialistas" in json_final["externo"]
            ):
                mapa_especialistas = {
                    item["nombre"]: item["carpeta_id"] for item in subcarpetas_externos["especialistas"]
                }
                for especialista in json_final["externo"]["especialistas"]:
                    nombre = obtener_nombre_elemento(especialista)
                    if nombre in mapa_especialistas:
                        especialista["id_folder"] = mapa_especialistas[nombre]

            # Mapear conductores
            if (
                "conductores" in subcarpetas_externos
                and "externo" in json_final
                and "conductores" in json_final["externo"]
            ):
                mapa_conductores = {
                    item["nombre"]: item["carpeta_id"] for item in subcarpetas_externos["conductores"]
                }
                for conductor in json_final["externo"]["conductores"]:
                    nombre = obtener_nombre_elemento(conductor)
                    if nombre in mapa_conductores:
                        conductor["id_folder"] = mapa_conductores[nombre]

            # Mapear vehiculos
            if "vehiculos" in subcarpetas_externos and "externo" in json_final and "vehiculos" in json_final["externo"]:
                mapa_vehiculos = {
                    obtener_nombre_elemento(item): item["carpeta_id"]
                    for item in subcarpetas_externos["vehiculos"]
                }
                for vehiculo in json_final["externo"]["vehiculos"]:
                    nombre = obtener_nombre_elemento(vehiculo)
                    if nombre in mapa_vehiculos:
                        vehiculo["id_folder"] = mapa_vehiculos[nombre]

        # Agregar id_folder a los datos MYMA
        if resultado_carpetas_myma and "subcarpetas_creadas" in resultado_carpetas_myma:
            subcarpetas_myma = resultado_carpetas_myma["subcarpetas_creadas"]

            # Mapear especialistas
            if "especialistas" in subcarpetas_myma and "myma" in json_final and "especialistas" in json_final["myma"]:
                mapa_especialistas = {
                    item["nombre"]: item["carpeta_id"] for item in subcarpetas_myma["especialistas"]
                }
                for especialista in json_final["myma"]["especialistas"]:
                    nombre = obtener_nombre_elemento(especialista)
                    if nombre in mapa_especialistas:
                        especialista["id_folder"] = mapa_especialistas[nombre]

            # Mapear conductores
            if "conductores" in subcarpetas_myma and "myma" in json_final and "conductores" in json_final["myma"]:
                mapa_conductores = {
                    item["nombre"]: item["carpeta_id"] for item in subcarpetas_myma["conductores"]
                }
                for conductor in json_final["myma"]["conductores"]:
                    nombre = obtener_nombre_elemento(conductor)
                    if nombre in mapa_conductores:
                        conductor["id_folder"] = mapa_conductores[nombre]

            # Mapear vehiculos
            if "vehiculos" in subcarpetas_myma and "myma" in json_final and "vehiculos" in json_final["myma"]:
                mapa_vehiculos = {
                    obtener_nombre_elemento(item): item["carpeta_id"]
                    for item in subcarpetas_myma["vehiculos"]
                }
                for vehiculo in json_final["myma"]["vehiculos"]:
                    nombre = obtener_nombre_elemento(vehiculo)
                    if nombre in mapa_vehiculos:
                        vehiculo["id_folder"] = mapa_vehiculos[nombre]

        return json_final

