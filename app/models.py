"""Modelos Pydantic para request y response."""
from pydantic import BaseModel, Field, validator
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
    empresa: Optional[str] = None
    especialistas: List[Especialista] = []
    conductores: List[Conductor] = []
    vehiculos: List[Vehiculo] = []


class ProyectoRequest(BaseModel):
    codigo_proyecto: str = Field(..., description="Codigo del proyecto")
    myma: DatosMyma
    externo: DatosExterno

    @validator("codigo_proyecto")
    def validar_codigo_proyecto(cls, value: str) -> str:
        """Valida que codigo_proyecto sea un string no vacio tras trim."""
        cleaned_value = (value or "").strip()
        if not cleaned_value:
            raise ValueError("codigo_proyecto no puede estar vacio")
        return cleaned_value


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


