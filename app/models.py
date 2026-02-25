"""Modelos Pydantic para request y response."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Especialista(BaseModel):
    id: int
    nombre: str
    id_folder: Optional[str] = None


class Conductor(BaseModel):
    id: int
    nombre: str
    id_folder: Optional[str] = None


class Vehiculo(BaseModel):
    id: Optional[int] = None
    patente: str
    id_folder: Optional[str] = None


class DatosMyma(BaseModel):
    especialistas: List[Especialista] = []
    conductores: List[Conductor] = []
    vehiculos: List[Vehiculo] = []


class DatosExterno(BaseModel):
    empresa: str
    especialistas: List[Especialista] = []
    conductores: List[Conductor] = []
    vehiculos: List[Vehiculo] = []


class ProyectoRequest(BaseModel):
    codigo_proyecto: str = Field(..., pattern=r'^MY-\d{3}-\d{4}$', description="Código del proyecto en formato MY-XXX-YYYY")
    myma: DatosMyma
    externo: DatosExterno


class ProyectoResponse(BaseModel):
    codigo_proyecto: str
    año_proyecto: str
    nombre_drive: str
    drive_id: str
    id_carpeta_final: Optional[str] = None
    json_final: Dict[str, Any]
    carpetas_externos: Optional[Dict[str, Any]] = None
    carpetas_myma: Optional[Dict[str, Any]] = None
    actualizaciones_supabase: Optional[Dict[str, Any]] = None
    mensaje: str = "Proceso completado exitosamente"


class ErrorResponse(BaseModel):
    error: str
    detalle: Optional[str] = None

