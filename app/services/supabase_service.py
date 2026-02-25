"""Servicio para interactuar con Supabase."""
import logging
import time
from typing import Any, Dict, Optional

from supabase import Client, create_client

from app.config import ENV_FILE_PATH, settings

logger = logging.getLogger(__name__)


class SupabaseService:
    """Servicio para interactuar con Supabase."""

    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        self.supabase_url = supabase_url or settings.supabase_url
        self.supabase_key = supabase_key or settings.supabase_key
        self.supabase: Optional[Client] = None
        self.config_diagnostico = self._build_config_diagnostico()

        if self.supabase_url and self.supabase_key:
            try:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            except Exception as error:
                self.config_diagnostico["create_client_error"] = str(error)
                logger.error(f"No se pudo crear cliente Supabase: {error}")

    @staticmethod
    def _mask_url(value: Optional[str]) -> Optional[str]:
        """Entrega una vista parcial de la URL sin exponer datos sensibles."""
        if not value:
            return None
        if len(value) <= 12:
            return value
        return f"{value[:8]}...{value[-4:]}"

    def _build_config_diagnostico(self) -> Dict[str, Any]:
        """Genera diagnostico de configuracion sin exponer secretos."""
        return {
            "supabase_url_configurada": bool(self.supabase_url),
            "supabase_key_configurada": bool(self.supabase_key),
            "supabase_url_preview": self._mask_url(self.supabase_url),
            "supabase_key_len": len(self.supabase_key) if self.supabase_key else 0,
            "env_file_path": str(ENV_FILE_PATH),
            "env_file_existe": ENV_FILE_PATH.exists(),
        }

    @staticmethod
    def _seccion_resultados_base() -> Dict[str, Any]:
        """Estructura base para reportar resultados por seccion."""
        return {
            "intentados": 0,
            "exitosos": 0,
            "no_encontrado": 0,
            "fallidos": 0,
            "omitidos_sin_id": 0,
            "omitidos_sin_id_folder": 0,
            "errores": [],
        }

    @staticmethod
    def _es_error_transitorio(error: Exception) -> bool:
        """Determina si un error es transitorio para reintentar."""
        error_texto = str(error).lower()
        patrones_transitorios = [
            "timeout",
            "timed out",
            "temporarily unavailable",
            "connection reset",
            "connection aborted",
            "network is unreachable",
            "service unavailable",
        ]
        return any(patron in error_texto for patron in patrones_transitorios)

    def _actualizar_registro(
        self,
        seccion_resultado: Dict[str, Any],
        tabla: str,
        registro: Dict[str, Any],
        etiqueta: str,
        max_reintentos: int = 3,
    ) -> None:
        """Actualiza un registro con diagnostico detallado y reintentos."""
        registro_id = registro.get("id")
        id_folder = registro.get("id_folder")
        nombre = registro.get("nombre") or registro.get("patente") or "N/A"

        if registro_id is None:
            seccion_resultado["omitidos_sin_id"] += 1
            return

        if not id_folder:
            seccion_resultado["omitidos_sin_id_folder"] += 1
            return

        seccion_resultado["intentados"] += 1
        ultimo_error: Optional[Exception] = None

        for intento in range(1, max_reintentos + 1):
            try:
                response = (
                    self.supabase.table(tabla)
                    .update({"drive_folder_id": id_folder}, count="exact")
                    .eq("id", registro_id)
                    .execute()
                )

                afectados = response.count if response.count is not None else len(response.data or [])

                if afectados > 0:
                    seccion_resultado["exitosos"] += 1
                    logger.info(
                        f"Actualizado {etiqueta} {nombre} (ID: {registro_id}) en {tabla}. "
                        f"Filas afectadas: {afectados}"
                    )
                else:
                    seccion_resultado["no_encontrado"] += 1
                    seccion_resultado["errores"].append(
                        {
                            "id": registro_id,
                            "nombre": nombre,
                            "tabla": tabla,
                            "error": "No se encontro registro para actualizar",
                        }
                    )
                    logger.warning(
                        f"No se encontro registro para {etiqueta} {nombre} (ID: {registro_id}) "
                        f"en tabla {tabla}."
                    )
                return
            except Exception as error:
                ultimo_error = error
                if intento < max_reintentos and self._es_error_transitorio(error):
                    espera = 0.5 * (2 ** (intento - 1))
                    logger.warning(
                        f"Error transitorio actualizando {etiqueta} {nombre} (ID: {registro_id}) "
                        f"en {tabla}. Reintento {intento}/{max_reintentos} en {espera:.1f}s. "
                        f"Error: {error}"
                    )
                    time.sleep(espera)
                    continue
                break

        seccion_resultado["fallidos"] += 1
        seccion_resultado["errores"].append(
            {
                "id": registro_id,
                "nombre": nombre,
                "tabla": tabla,
                "error": str(ultimo_error),
                "max_reintentos": max_reintentos,
            }
        )
        logger.error(
            f"Error actualizando {etiqueta} {nombre} (ID: {registro_id}) en tabla {tabla}: {ultimo_error}"
        )

    def actualizar_drive_folder_ids(self, json_final: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza los campos drive_folder_id en Supabase usando los valores del JSON final.

        Args:
            json_final: Diccionario con la estructura final (con id_folder en cada registro).

        Returns:
            Diccionario con diagnostico detallado de actualizaciones.
        """
        if not self.supabase:
            logger.warning("Supabase no esta configurado. No se actualizaran los drive_folder_id.")
            return {
                "estado": "sin_configuracion_supabase",
                "diagnostico_configuracion": self.config_diagnostico,
                "especialistas_myma": self._seccion_resultados_base(),
                "especialistas_externo": self._seccion_resultados_base(),
                "conductores_myma": self._seccion_resultados_base(),
                "conductores_externo": self._seccion_resultados_base(),
                "vehiculos_myma": self._seccion_resultados_base(),
                "vehiculos_externo": self._seccion_resultados_base(),
                "resumen": {
                    "intentados": 0,
                    "exitosos": 0,
                    "no_encontrado": 0,
                    "fallidos": 0,
                    "omitidos_sin_id": 0,
                    "omitidos_sin_id_folder": 0,
                },
            }

        resultados = {
            "estado": "ok",
            "especialistas_myma": self._seccion_resultados_base(),
            "especialistas_externo": self._seccion_resultados_base(),
            "conductores_myma": self._seccion_resultados_base(),
            "conductores_externo": self._seccion_resultados_base(),
            "vehiculos_myma": self._seccion_resultados_base(),
            "vehiculos_externo": self._seccion_resultados_base(),
        }

        if "myma" in json_final and "especialistas" in json_final["myma"]:
            for especialista in json_final["myma"]["especialistas"]:
                self._actualizar_registro(
                    seccion_resultado=resultados["especialistas_myma"],
                    tabla="fct_acreditacion_solicitud_trabajador_manual",
                    registro=especialista,
                    etiqueta="especialista MYMA",
                )

        if "externo" in json_final and "especialistas" in json_final["externo"]:
            for especialista in json_final["externo"]["especialistas"]:
                self._actualizar_registro(
                    seccion_resultado=resultados["especialistas_externo"],
                    tabla="fct_acreditacion_solicitud_trabajador_manual",
                    registro=especialista,
                    etiqueta="especialista Externo",
                )

        if "myma" in json_final and "conductores" in json_final["myma"]:
            for conductor in json_final["myma"]["conductores"]:
                self._actualizar_registro(
                    seccion_resultado=resultados["conductores_myma"],
                    tabla="fct_acreditacion_solicitud_conductor_manual",
                    registro=conductor,
                    etiqueta="conductor MYMA",
                )

        if "externo" in json_final and "conductores" in json_final["externo"]:
            for conductor in json_final["externo"]["conductores"]:
                self._actualizar_registro(
                    seccion_resultado=resultados["conductores_externo"],
                    tabla="fct_acreditacion_solicitud_conductor_manual",
                    registro=conductor,
                    etiqueta="conductor Externo",
                )

        if "myma" in json_final and "vehiculos" in json_final["myma"]:
            for vehiculo in json_final["myma"]["vehiculos"]:
                self._actualizar_registro(
                    seccion_resultado=resultados["vehiculos_myma"],
                    tabla="fct_acreditacion_solicitud_vehiculos",
                    registro=vehiculo,
                    etiqueta="vehiculo MYMA",
                )

        if "externo" in json_final and "vehiculos" in json_final["externo"]:
            for vehiculo in json_final["externo"]["vehiculos"]:
                self._actualizar_registro(
                    seccion_resultado=resultados["vehiculos_externo"],
                    tabla="fct_acreditacion_solicitud_vehiculos",
                    registro=vehiculo,
                    etiqueta="vehiculo Externo",
                )

        secciones = [
            "especialistas_myma",
            "especialistas_externo",
            "conductores_myma",
            "conductores_externo",
            "vehiculos_myma",
            "vehiculos_externo",
        ]
        resultados["resumen"] = {
            "intentados": sum(resultados[s]["intentados"] for s in secciones),
            "exitosos": sum(resultados[s]["exitosos"] for s in secciones),
            "no_encontrado": sum(resultados[s]["no_encontrado"] for s in secciones),
            "fallidos": sum(resultados[s]["fallidos"] for s in secciones),
            "omitidos_sin_id": sum(resultados[s]["omitidos_sin_id"] for s in secciones),
            "omitidos_sin_id_folder": sum(resultados[s]["omitidos_sin_id_folder"] for s in secciones),
        }

        if resultados["resumen"]["intentados"] > 0 and resultados["resumen"]["exitosos"] == 0:
            logger.warning(
                "Se intentaron actualizaciones en Supabase, pero no hubo filas afectadas. "
                f"Resumen: {resultados['resumen']}"
            )

        return resultados
