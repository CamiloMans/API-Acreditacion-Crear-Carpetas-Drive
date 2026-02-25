"""Funciones auxiliares para el procesamiento de datos."""


def obtener_nombre_elemento(elemento):
    """
    Extrae el identificador legible de un elemento.
    Soporta objetos con 'nombre' (personas) o 'patente' (vehiculos).
    Compatible con string para mantener retrocompatibilidad.
    
    Args:
        elemento: Puede ser un string o un diccionario con 'nombre'/'patente'
    
    Returns:
        El valor legible como string
    """
    if isinstance(elemento, dict) and 'nombre' in elemento:
        return elemento['nombre']
    elif isinstance(elemento, dict) and 'patente' in elemento:
        return elemento['patente']
    elif isinstance(elemento, str):
        return elemento
    else:
        return str(elemento)


def obtener_id_elemento(elemento):
    """
    Extrae el id de un elemento si está disponible.
    
    Args:
        elemento: Puede ser un string o un diccionario con 'id'
    
    Returns:
        El id si está disponible, None si no
    """
    if isinstance(elemento, dict) and 'id' in elemento:
        return elemento['id']
    return None

