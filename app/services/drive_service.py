"""Servicio para interactuar con Google Drive API."""
import os
import json
import re
import logging
from typing import Optional, Dict, Any, List, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings
from app.utils.helpers import obtener_nombre_elemento, obtener_id_elemento

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveService:
    """Servicio para interactuar con Google Drive API."""
    
    def __init__(self, token_file: Optional[str] = None):
        self.token_file = token_file or settings.google_token_file
        self.service = None
    
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
                results = service.drives().list(
                    pageSize=100,
                    pageToken=page_token
                ).execute()
                
                drives = results.get('drives', [])
                for drive in drives:
                    if drive['name'] == drive_name:
                        return drive['id']
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as e:
                logger.error(f"Error buscando Shared Drive: {e}")
                break
        
        return None
    
    def list_folders_in_directory(self, parent_id: str, drive_id: Optional[str] = None, max_results: int = 1000) -> List[Tuple[str, str]]:
        """Lista todas las carpetas dentro de un directorio específico."""
        service = self.get_service()
        folders = []
        page_token = None
        
        if drive_id and parent_id == drive_id:
            query = f"mimeType = 'application/vnd.google-apps.folder' and '{drive_id}' in parents and trashed = false"
        else:
            query = f"mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed = false"
        
        while True:
            try:
                params = {
                    'q': query,
                    'spaces': 'drive',
                    'fields': 'nextPageToken, files(id, name, parents)',
                    'pageToken': page_token,
                    'pageSize': 100,
                    'orderBy': 'name',
                    'supportsAllDrives': True,
                    'includeItemsFromAllDrives': True
                }
                
                if drive_id:
                    params['driveId'] = drive_id
                    params['corpora'] = 'drive'
                
                results = service.files().list(**params).execute()
                
                files = results.get('files', [])
                for file in files:
                    folders.append((file['name'], file['id']))
                    if len(folders) >= max_results:
                        return folders
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as e:
                logger.error(f"Error listando carpetas: {e}")
                break
        
        return folders
    
    def find_folder_by_name_in_directory(self, folder_name: str, parent_id: str, drive_id: Optional[str] = None) -> Optional[str]:
        """Busca una carpeta por nombre dentro de un directorio específico."""
        service = self.get_service()
        escaped_name = folder_name.replace("'", "\\'")
        
        if drive_id and parent_id == drive_id:
            query = f"name = '{escaped_name}' and mimeType = 'application/vnd.google-apps.folder' and '{drive_id}' in parents and trashed = false"
        else:
            query = f"name = '{escaped_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed = false"
        
        page_token = None
        
        while True:
            try:
                params = {
                    'q': query,
                    'spaces': 'drive',
                    'fields': 'nextPageToken, files(id, name, parents)',
                    'pageToken': page_token,
                    'pageSize': 100,
                    'supportsAllDrives': True,
                    'includeItemsFromAllDrives': True
                }
                
                if drive_id:
                    params['driveId'] = drive_id
                    params['corpora'] = 'drive'
                
                results = service.files().list(**params).execute()
                
                files = results.get('files', [])
                for file in files:
                    if file['name'] == folder_name:
                        parents = file.get('parents', [])
                        if drive_id and parent_id == drive_id:
                            if drive_id in parents or not parents:
                                return file['id']
                        else:
                            if parent_id in parents:
                                return file['id']
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as e:
                logger.error(f"Error buscando carpeta '{folder_name}': {e}")
                break
        
        return None
    
    def find_folder_containing_name(self, folder_name_part: str, parent_id: str, drive_id: Optional[str] = None) -> Optional[str]:
        """Busca una carpeta que contenga un texto específico en su nombre."""
        carpetas = self.list_folders_in_directory(parent_id, drive_id)
        
        for nombre, carpeta_id in carpetas:
            if folder_name_part.lower() in nombre.lower():
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
        """Procesa los datos del proyecto y busca el Shared Drive correspondiente."""
        if isinstance(datos_proyecto, str):
            codigo_proyecto = datos_proyecto
            datos_completos = None
        elif isinstance(datos_proyecto, dict):
            if 'codigo_proyecto' not in datos_proyecto:
                logger.error("El diccionario debe contener 'codigo_proyecto'")
                return None
            codigo_proyecto = datos_proyecto['codigo_proyecto']
            datos_completos = datos_proyecto
        else:
            logger.error("datos_proyecto debe ser un diccionario o un string")
            return None
        
        patron = r'^MY-\d{3}-(\d{4})$'
        match = re.match(patron, codigo_proyecto)
        
        if not match:
            logger.error(f"El código '{codigo_proyecto}' no tiene el formato correcto.")
            return None
        
        año_proyecto = match.group(1)
        nombre_drive = f"Proyectos {año_proyecto}"
        
        drive_id = self.find_shared_drive_by_name(nombre_drive)
        
        if not drive_id:
            logger.error(f"No se encontró el Shared Drive '{nombre_drive}'")
            return None
        
        carpetas = self.list_folders_in_directory(drive_id, drive_id)
        
        resultado = {
            'codigo_proyecto': codigo_proyecto,
            'año_proyecto': año_proyecto,
            'nombre_drive': nombre_drive,
            'drive_id': drive_id,
            'carpetas': carpetas
        }
        
        if datos_completos:
            resultado['datos_completos'] = datos_completos
        
        return resultado
    
    def navegar_ruta_proyecto(self, codigo_proyecto: str, drive_id: str, ruta_fija: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Navega por la ruta del proyecto para obtener el ID de la última carpeta."""
        if ruta_fija is None:
            ruta_fija = ["08 Terrenos", "03 Acreditación y Arranque", "01 Acreditación"]
        
        carpeta_proyecto_id = self.find_folder_by_name_in_directory(codigo_proyecto, drive_id, drive_id)
        
        if not carpeta_proyecto_id:
            logger.error(f"No se encontró la carpeta '{codigo_proyecto}' en el Shared Drive")
            return None
        
        current_parent_id = carpeta_proyecto_id
        navigation_info = {
            'codigo_proyecto': codigo_proyecto,
            'carpeta_proyecto_id': carpeta_proyecto_id,
            'niveles': []
        }
        
        for i, nombre_carpeta in enumerate(ruta_fija, 1):
            carpeta_id = self.find_folder_by_name_in_directory(nombre_carpeta, current_parent_id, drive_id)
            
            if carpeta_id:
                navigation_info['niveles'].append({
                    'nombre': nombre_carpeta,
                    'id': carpeta_id,
                    'parent_id': current_parent_id,
                    'nivel': i
                })
                current_parent_id = carpeta_id
            else:
                logger.error(f"Carpeta '{nombre_carpeta}' NO encontrada en este directorio")
                navigation_info['niveles'].append({
                    'nombre': nombre_carpeta,
                    'id': None,
                    'parent_id': current_parent_id,
                    'nivel': i,
                    'error': 'Carpeta no encontrada'
                })
                break
        
        if navigation_info['niveles']:
            ultimo_nivel = navigation_info['niveles'][-1]
            if ultimo_nivel.get('id'):
                navigation_info['id_carpeta_final'] = ultimo_nivel['id']
            else:
                navigation_info['id_carpeta_final'] = None
        else:
            navigation_info['id_carpeta_final'] = None
        
        return navigation_info
    
    def gestionar_carpetas_externos(self, id_carpeta_acreditacion: str, datos_externos: Dict[str, Any], drive_id: str) -> Dict[str, Any]:
        """Gestiona las carpetas para los datos externos dentro de '01 Acreditación'."""
        carpetas_acreditacion = self.list_folders_in_directory(id_carpeta_acreditacion, drive_id)
        
        carpeta_externos_id = self.find_folder_containing_name("Externos", id_carpeta_acreditacion, drive_id)
        
        if not carpeta_externos_id:
            carpeta_externos_id = self.create_folder("Externos", id_carpeta_acreditacion, drive_id)
        
        if not datos_externos or 'empresa' not in datos_externos:
            return {
                'carpeta_externos_id': carpeta_externos_id,
                'carpeta_empresa_id': None,
                'carpetas_creadas': []
            }
        
        empresa_nombre = datos_externos['empresa']
        carpeta_empresa_id = self.find_folder_by_name_in_directory(empresa_nombre, carpeta_externos_id, drive_id)
        
        if not carpeta_empresa_id:
            carpeta_empresa_id = self.create_folder(empresa_nombre, carpeta_externos_id, drive_id)
        
        carpetas_a_crear = ["01 Empresa", "02 Especialistas", "03 Conductores", "04 Vehiculos"]
        carpetas_creadas = {}
        
        for nombre_carpeta in carpetas_a_crear:
            carpeta_existente = self.find_folder_by_name_in_directory(nombre_carpeta, carpeta_empresa_id, drive_id)
            if carpeta_existente:
                carpetas_creadas[nombre_carpeta] = carpeta_existente
            else:
                carpeta_id = self.create_folder(nombre_carpeta, carpeta_empresa_id, drive_id)
                carpetas_creadas[nombre_carpeta] = carpeta_id
        
        subcarpetas_creadas = {}
        
        # Crear carpetas para especialistas
        if 'especialistas' in datos_externos and datos_externos['especialistas']:
            carpeta_especialistas_id = carpetas_creadas.get("02 Especialistas")
            if carpeta_especialistas_id:
                subcarpetas_creadas['especialistas'] = []
                for elemento in datos_externos['especialistas']:
                    nombre_especialista = obtener_nombre_elemento(elemento)
                    id_especialista = obtener_id_elemento(elemento)
                    
                    carpeta_existente = self.find_folder_by_name_in_directory(
                        nombre_especialista, carpeta_especialistas_id, drive_id
                    )
                    if carpeta_existente:
                        item = {'nombre': nombre_especialista, 'carpeta_id': carpeta_existente}
                        if id_especialista is not None:
                            item['id'] = id_especialista
                        subcarpetas_creadas['especialistas'].append(item)
                    else:
                        carpeta_id = self.create_folder(nombre_especialista, carpeta_especialistas_id, drive_id)
                        item = {'nombre': nombre_especialista, 'carpeta_id': carpeta_id}
                        if id_especialista is not None:
                            item['id'] = id_especialista
                        subcarpetas_creadas['especialistas'].append(item)
        
        # Crear carpetas para conductores
        if 'conductores' in datos_externos and datos_externos['conductores']:
            carpeta_conductores_id = carpetas_creadas.get("03 Conductores")
            if carpeta_conductores_id:
                subcarpetas_creadas['conductores'] = []
                for elemento in datos_externos['conductores']:
                    nombre_conductor = obtener_nombre_elemento(elemento)
                    id_conductor = obtener_id_elemento(elemento)
                    
                    carpeta_existente = self.find_folder_by_name_in_directory(
                        nombre_conductor, carpeta_conductores_id, drive_id
                    )
                    if carpeta_existente:
                        item = {'nombre': nombre_conductor, 'carpeta_id': carpeta_existente}
                        if id_conductor is not None:
                            item['id'] = id_conductor
                        subcarpetas_creadas['conductores'].append(item)
                    else:
                        carpeta_id = self.create_folder(nombre_conductor, carpeta_conductores_id, drive_id)
                        item = {'nombre': nombre_conductor, 'carpeta_id': carpeta_id}
                        if id_conductor is not None:
                            item['id'] = id_conductor
                        subcarpetas_creadas['conductores'].append(item)
        
        # Crear carpetas para vehículos
        if 'vehiculos' in datos_externos and datos_externos['vehiculos']:
            carpeta_vehiculos_id = carpetas_creadas.get("04 Vehiculos")
            if carpeta_vehiculos_id:
                subcarpetas_creadas['vehiculos'] = []
                for elemento in datos_externos['vehiculos']:
                    nombre_vehiculo = obtener_nombre_elemento(elemento)
                    id_vehiculo = obtener_id_elemento(elemento)
                    
                    carpeta_existente = self.find_folder_by_name_in_directory(
                        nombre_vehiculo, carpeta_vehiculos_id, drive_id
                    )
                    if carpeta_existente:
                        item = {'nombre': nombre_vehiculo, 'carpeta_id': carpeta_existente}
                        if id_vehiculo is not None:
                            item['id'] = id_vehiculo
                        subcarpetas_creadas['vehiculos'].append(item)
                    else:
                        carpeta_id = self.create_folder(nombre_vehiculo, carpeta_vehiculos_id, drive_id)
                        item = {'nombre': nombre_vehiculo, 'carpeta_id': carpeta_id}
                        if id_vehiculo is not None:
                            item['id'] = id_vehiculo
                        subcarpetas_creadas['vehiculos'].append(item)
        
        return {
            'carpeta_externos_id': carpeta_externos_id,
            'carpeta_empresa_id': carpeta_empresa_id,
            'carpetas_creadas': carpetas_creadas,
            'subcarpetas_creadas': subcarpetas_creadas
        }
    
    def gestionar_carpetas_myma(self, id_carpeta_acreditacion: str, datos_myma: Dict[str, Any], drive_id: str) -> Dict[str, Any]:
        """Gestiona las subcarpetas para los datos MYMA dentro de '01 Acreditación'."""
        carpeta_myma_id = self.find_folder_containing_name("MYMA", id_carpeta_acreditacion, drive_id)
        
        if not carpeta_myma_id:
            return {
                'carpeta_myma_id': None,
                'subcarpetas_creadas': {}
            }
        
        subcarpetas_creadas = {}
        
        # Crear carpetas para especialistas
        if 'especialistas' in datos_myma and datos_myma['especialistas']:
            carpeta_especialistas_id = self.find_folder_containing_name("Especialistas", carpeta_myma_id, drive_id)
            if carpeta_especialistas_id:
                subcarpetas_creadas['especialistas'] = []
                for elemento in datos_myma['especialistas']:
                    nombre_especialista = obtener_nombre_elemento(elemento)
                    id_especialista = obtener_id_elemento(elemento)
                    
                    carpeta_existente = self.find_folder_by_name_in_directory(
                        nombre_especialista, carpeta_especialistas_id, drive_id
                    )
                    if carpeta_existente:
                        item = {'nombre': nombre_especialista, 'carpeta_id': carpeta_existente}
                        if id_especialista is not None:
                            item['id'] = id_especialista
                        subcarpetas_creadas['especialistas'].append(item)
                    else:
                        carpeta_id = self.create_folder(nombre_especialista, carpeta_especialistas_id, drive_id)
                        item = {'nombre': nombre_especialista, 'carpeta_id': carpeta_id}
                        if id_especialista is not None:
                            item['id'] = id_especialista
                        subcarpetas_creadas['especialistas'].append(item)
        
        # Crear carpetas para conductores
        if 'conductores' in datos_myma and datos_myma['conductores']:
            carpeta_conductores_id = self.find_folder_containing_name("Conductores", carpeta_myma_id, drive_id)
            if carpeta_conductores_id:
                subcarpetas_creadas['conductores'] = []
                for elemento in datos_myma['conductores']:
                    nombre_conductor = obtener_nombre_elemento(elemento)
                    id_conductor = obtener_id_elemento(elemento)
                    
                    carpeta_existente = self.find_folder_by_name_in_directory(
                        nombre_conductor, carpeta_conductores_id, drive_id
                    )
                    if carpeta_existente:
                        item = {'nombre': nombre_conductor, 'carpeta_id': carpeta_existente}
                        if id_conductor is not None:
                            item['id'] = id_conductor
                        subcarpetas_creadas['conductores'].append(item)
                    else:
                        carpeta_id = self.create_folder(nombre_conductor, carpeta_conductores_id, drive_id)
                        item = {'nombre': nombre_conductor, 'carpeta_id': carpeta_id}
                        if id_conductor is not None:
                            item['id'] = id_conductor
                        subcarpetas_creadas['conductores'].append(item)
        
        # Crear carpetas para vehículos
        if 'vehiculos' in datos_myma and datos_myma['vehiculos']:
            carpeta_vehiculos_id = self.find_folder_containing_name("Vehiculos", carpeta_myma_id, drive_id)
            if carpeta_vehiculos_id:
                subcarpetas_creadas['vehiculos'] = []
                for elemento in datos_myma['vehiculos']:
                    nombre_vehiculo = obtener_nombre_elemento(elemento)
                    id_vehiculo = obtener_id_elemento(elemento)
                    
                    carpeta_existente = self.find_folder_by_name_in_directory(
                        nombre_vehiculo, carpeta_vehiculos_id, drive_id
                    )
                    if carpeta_existente:
                        item = {'nombre': nombre_vehiculo, 'carpeta_id': carpeta_existente}
                        if id_vehiculo is not None:
                            item['id'] = id_vehiculo
                        subcarpetas_creadas['vehiculos'].append(item)
                    else:
                        carpeta_id = self.create_folder(nombre_vehiculo, carpeta_vehiculos_id, drive_id)
                        item = {'nombre': nombre_vehiculo, 'carpeta_id': carpeta_id}
                        if id_vehiculo is not None:
                            item['id'] = id_vehiculo
                        subcarpetas_creadas['vehiculos'].append(item)
        
        return {
            'carpeta_myma_id': carpeta_myma_id,
            'subcarpetas_creadas': subcarpetas_creadas
        }
    
    def generar_json_final(self, datos_proyecto: Dict[str, Any], resultado_carpetas_externos: Optional[Dict[str, Any]] = None, resultado_carpetas_myma: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Genera el JSON final con el id_folder de cada registro."""
        json_final = json.loads(json.dumps(datos_proyecto))
        
        # Agregar id_folder a los datos externos
        if resultado_carpetas_externos and 'subcarpetas_creadas' in resultado_carpetas_externos:
            subcarpetas_externos = resultado_carpetas_externos['subcarpetas_creadas']
            
            # Mapear especialistas
            if 'especialistas' in subcarpetas_externos and 'externo' in json_final and 'especialistas' in json_final['externo']:
                mapa_especialistas = {item['nombre']: item['carpeta_id'] for item in subcarpetas_externos['especialistas']}
                for especialista in json_final['externo']['especialistas']:
                    nombre = obtener_nombre_elemento(especialista)
                    if nombre in mapa_especialistas:
                        especialista['id_folder'] = mapa_especialistas[nombre]
            
            # Mapear conductores
            if 'conductores' in subcarpetas_externos and 'externo' in json_final and 'conductores' in json_final['externo']:
                mapa_conductores = {item['nombre']: item['carpeta_id'] for item in subcarpetas_externos['conductores']}
                for conductor in json_final['externo']['conductores']:
                    nombre = obtener_nombre_elemento(conductor)
                    if nombre in mapa_conductores:
                        conductor['id_folder'] = mapa_conductores[nombre]
            
            # Mapear vehículos
            if 'vehiculos' in subcarpetas_externos and 'externo' in json_final and 'vehiculos' in json_final['externo']:
                mapa_vehiculos = {item['nombre']: item['carpeta_id'] for item in subcarpetas_externos['vehiculos']}
                for vehiculo in json_final['externo']['vehiculos']:
                    nombre = obtener_nombre_elemento(vehiculo)
                    if nombre in mapa_vehiculos:
                        vehiculo['id_folder'] = mapa_vehiculos[nombre]
        
        # Agregar id_folder a los datos MYMA
        if resultado_carpetas_myma and 'subcarpetas_creadas' in resultado_carpetas_myma:
            subcarpetas_myma = resultado_carpetas_myma['subcarpetas_creadas']
            
            # Mapear especialistas
            if 'especialistas' in subcarpetas_myma and 'myma' in json_final and 'especialistas' in json_final['myma']:
                mapa_especialistas = {item['nombre']: item['carpeta_id'] for item in subcarpetas_myma['especialistas']}
                for especialista in json_final['myma']['especialistas']:
                    nombre = obtener_nombre_elemento(especialista)
                    if nombre in mapa_especialistas:
                        especialista['id_folder'] = mapa_especialistas[nombre]
            
            # Mapear conductores
            if 'conductores' in subcarpetas_myma and 'myma' in json_final and 'conductores' in json_final['myma']:
                mapa_conductores = {item['nombre']: item['carpeta_id'] for item in subcarpetas_myma['conductores']}
                for conductor in json_final['myma']['conductores']:
                    nombre = obtener_nombre_elemento(conductor)
                    if nombre in mapa_conductores:
                        conductor['id_folder'] = mapa_conductores[nombre]
            
            # Mapear vehículos
            if 'vehiculos' in subcarpetas_myma and 'myma' in json_final and 'vehiculos' in json_final['myma']:
                mapa_vehiculos = {item['nombre']: item['carpeta_id'] for item in subcarpetas_myma['vehiculos']}
                for vehiculo in json_final['myma']['vehiculos']:
                    nombre = obtener_nombre_elemento(vehiculo)
                    if nombre in mapa_vehiculos:
                        vehiculo['id_folder'] = mapa_vehiculos[nombre]
        
        return json_final
