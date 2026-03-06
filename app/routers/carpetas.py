"""Router para endpoints de carpetas."""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.models import ProyectoRequest, ProyectoResponse
from app.services.drive_service import DriveService
from app.services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/carpetas", tags=["carpetas"])


def get_drive_service() -> DriveService:
    """Dependency para obtener el servicio de Drive."""
    return DriveService()


def get_supabase_service() -> SupabaseService:
    """Dependency para obtener el servicio de Supabase."""
    return SupabaseService()


@router.post("/crear", response_model=ProyectoResponse)
async def crear_carpetas(
    proyecto: ProyectoRequest,
    drive_service: DriveService = Depends(get_drive_service),
    supabase_service: SupabaseService = Depends(get_supabase_service),
):
    """
    Endpoint principal que:
    1. Procesa el codigo del proyecto
    2. Navega por la ruta del proyecto
    3. Crea carpetas para datos externos y MYMA
    4. Genera el JSON final con id_folder
    5. Actualiza Supabase
    """
    try:
        # 1. Procesar codigo del proyecto
        logger.info(f"Procesando codigo de proyecto: {proyecto.codigo_proyecto}")
        resultado = drive_service.procesar_codigo_proyecto(proyecto.dict())
        if not resultado:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Error procesando codigo del proyecto. Verifique formato MY-XXX-YYYY, "
                    "existencia del Shared Drive 'Acreditaciones' y carpeta base "
                    "'Acreditaciones' dentro del drive."
                ),
            )

        # 2. Navegar ruta del proyecto
        logger.info(f"Navegando ruta del proyecto: {proyecto.codigo_proyecto}")
        resultado_navegacion = drive_service.navegar_ruta_proyecto(
            proyecto.codigo_proyecto,
            resultado["drive_id"],
        )
        if not resultado_navegacion or not resultado_navegacion.get("id_carpeta_final"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Error navegando ruta del proyecto. Verifique la estructura "
                    "Acreditaciones/Acreditaciones/Proyectos YYYY/<codigo_proyecto>."
                ),
            )

        id_carpeta_acreditacion = resultado_navegacion["id_carpeta_final"]

        # 3. Gestionar carpetas externos
        resultado_carpetas_externos: Dict[str, Any] | None = None
        if proyecto.externo and proyecto.externo.empresa:
            logger.info(
                f"Gestionando carpetas externos para empresa: {proyecto.externo.empresa}"
            )
            resultado_carpetas_externos = drive_service.gestionar_carpetas_externos(
                id_carpeta_acreditacion,
                proyecto.externo.dict(),
                resultado["drive_id"],
            )

        # 4. Gestionar carpetas MYMA
        resultado_carpetas_myma: Dict[str, Any] | None = None
        if proyecto.myma:
            logger.info("Gestionando carpetas MYMA")
            resultado_carpetas_myma = drive_service.gestionar_carpetas_myma(
                id_carpeta_acreditacion,
                proyecto.myma.dict(),
                resultado["drive_id"],
            )

        # 5. Generar JSON final
        logger.info("Generando JSON final con id_folder")
        json_final = drive_service.generar_json_final(
            proyecto.dict(),
            resultado_carpetas_externos,
            resultado_carpetas_myma,
        )

        # 6. Actualizar Supabase
        actualizaciones_supabase: Dict[str, Any] | None = None
        try:
            logger.info("Actualizando Supabase con drive_folder_id")
            actualizaciones_supabase = supabase_service.actualizar_drive_folder_ids(json_final)
            if isinstance(actualizaciones_supabase, dict):
                resumen = actualizaciones_supabase.get("resumen", {})
                intentados = resumen.get("intentados", 0)
                exitosos = resumen.get("exitosos", 0)
                if intentados > 0 and exitosos == 0:
                    logger.warning(
                        "Supabase no actualizo filas aunque hubo intentos. "
                        f"Resumen: {resumen}"
                    )
        except Exception as e:
            logger.warning(f"Error actualizando Supabase (continuando de todas formas): {e}")
            actualizaciones_supabase = {"error": str(e)}

        return ProyectoResponse(
            **{
                "codigo_proyecto": proyecto.codigo_proyecto,
                "a\u00f1o_proyecto": resultado["a\u00f1o_proyecto"],
                "nombre_drive": resultado["nombre_drive"],
                "drive_id": resultado["drive_id"],
                "id_carpeta_final": id_carpeta_acreditacion,
                "json_final": json_final,
                "carpetas_externos": resultado_carpetas_externos,
                "carpetas_myma": resultado_carpetas_myma,
                "actualizaciones_supabase": actualizaciones_supabase,
                "mensaje": "Proceso completado exitosamente",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en crear_carpetas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

