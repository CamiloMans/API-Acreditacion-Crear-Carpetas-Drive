# API Crear Carpetas Solicitud Acreditación

API FastAPI para crear carpetas en Google Drive y actualizar registros en Supabase para solicitudes de acreditación.

## Descripción

Esta API automatiza el proceso de:
1. Procesar códigos de proyecto en formato `MY-XXX-YYYY`
2. Buscar y navegar por Shared Drives de Google Drive
3. Crear estructura de carpetas para datos MYMA y externos
4. Generar JSON final con `id_folder` de cada registro
5. Actualizar tablas en Supabase con los `drive_folder_id`

## Requisitos Previos

- **Python 3.11.0** (recomendado y especificado en `runtime.txt`). Python 3.14 tiene problemas de compatibilidad con algunas dependencias.
- Cuenta de Google con acceso a Google Drive API
- Proyecto de Supabase configurado
- Archivo token OAuth (`token.json`) con `refresh_token` habilitado
**⚠️ IMPORTANTE - Versión de Python**: Este proyecto está configurado para usar **Python 3.11.0** (ver `runtime.txt`). Python 3.14 tiene problemas de compatibilidad con `httpcore` y otras dependencias. Si estás usando Python 3.14, se recomienda crear un nuevo entorno virtual con Python 3.11:

```bash
# En Windows, si tienes Python 3.11 instalado:
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Nota sobre Supabase**: Se usa la versión `2.0.0` de Supabase para evitar dependencias opcionales que requieren compilación C++ (como `pyiceberg` y `pyroaring`). Esta versión es suficiente para las funcionalidades básicas de actualización de datos que requiere esta API.

## Instalación

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd CrearCarpetasSolicitudAcreditacion
```

### 2. Verificar versión de Python

**⚠️ IMPORTANTE**: Este proyecto requiere **Python 3.11.0**. Si tienes Python 3.14, ver el archivo `SETUP_PYTHON311.md` para instrucciones de instalación.

```bash
python --version  # Debe mostrar Python 3.11.0
# O en Windows:
py -3.11 --version
```

### 3. Crear entorno virtual

```bash
# En Windows con Python 3.11:
py -3.11 -m venv .venv
.venv\Scripts\activate

# En Linux/Mac:
python3.11 -m venv .venv
source .venv/bin/activate
```

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5. Configurar variables de entorno

Copia el archivo `.env.example` a `.env` y completa las variables:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
# Google Drive Configuration
GOOGLE_TOKEN_FILE=token.json

# Supabase Configuration
SUPABASE_PROJECT_ID=pugasfsnckeyitjemvju
SUPABASE_URL=https://pugasfsnckeyitjemvju.supabase.co
SUPABASE_KEY=tu_supabase_key_aqui

# Application Configuration
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### 6. Configurar autenticacion de Google Drive

1. Genera `token.json` una sola vez en entorno local/controlado.
2. Verifica que el archivo incluya `refresh_token`, `client_id`, `client_secret`, `token_uri` y `scopes`.
3. Configura `GOOGLE_TOKEN_FILE` con la ruta del token que estara disponible en runtime.
4. En produccion no se ejecuta flujo OAuth interactivo (no navegador, no servidor HTTP local).

## Uso Local

### Ejecutar el servidor

**Opción 1: Usando uvicorn directamente (puede ser bloqueado por políticas de Windows)**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Opción 2: Usando Python -m (recomendado si uvicorn.exe está bloqueado)**
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Si Windows Application Control bloquea `uvicorn.exe`, usa la Opción 2.

La API estará disponible en `http://localhost:8000`

### Documentación Interactiva

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Ejemplo de Request

```bash
curl -X POST "http://localhost:8000/carpetas/crear" \
  -H "Content-Type: application/json" \
  -d '{
    "codigo_proyecto": "MY-000-2026",
    "myma": {
      "especialistas": [
        {"id": 192, "nombre": "Alan Flores"},
        {"id": 193, "nombre": "Angel Galaz"}
      ],
      "conductores": [
        {"id": 81, "nombre": "Pedrito"}
      ],
      "vehiculos": []
    },
    "externo": {
      "empresa": "AGQ",
      "especialistas": [
        {"id": 194, "nombre": "Daniel Rodriguez"},
        {"id": 195, "nombre": "Jaime Sepulveda"}
      ],
      "conductores": [
        {"id": 82, "nombre": "Diego"},
        {"id": 83, "nombre": "Joaquin"}
      ],
      "vehiculos": []
    }
  }'
```

### Ejemplo de Response

```json
{
  "codigo_proyecto": "MY-000-2026",
  "año_proyecto": "2026",
  "nombre_drive": "Proyectos 2026",
  "drive_id": "0AJ4V4Ts6OVe8Uk9PVA",
  "id_carpeta_final": "1cxsi-MHrX_5DnDaYddWDOSo3wnz2VV-l",
  "json_final": {
    "codigo_proyecto": "MY-000-2026",
    "myma": {
      "especialistas": [
        {"id": 192, "nombre": "Alan Flores", "id_folder": "1S7QEsiGLSqwRUHASH-jfrQe5QlqIvsCK"}
      ]
    },
    "externo": {
      "empresa": "AGQ",
      "especialistas": [
        {"id": 194, "nombre": "Daniel Rodriguez", "id_folder": "1LAa3nZGd_Tf3_xGvvD1ragKyjnOfaU1R"}
      ]
    }
  },
  "carpetas_externos": {...},
  "carpetas_myma": {...},
  "actualizaciones_supabase": {...},
  "mensaje": "Proceso completado exitosamente"
}
```

## Testing

Ejecutar tests:

```bash
pytest tests/
```

## Deployment en Render

### 1. Preparar el repositorio

Asegúrate de que todos los archivos estén commitados:

```bash
git add .
git commit -m "Preparar para deployment"
git push
```

### 2. Crear servicio en Render

1. Ve a [Render Dashboard](https://dashboard.render.com)
2. Click en "New" > "Web Service"
3. Conecta tu repositorio Git
4. Render detectará automáticamente `render.yaml`

### 3. Configurar variables de entorno

En el dashboard de Render, ve a "Environment" y agrega:

- `GOOGLE_TOKEN_FILE` - Ruta a un `token.json` existente y disponible en runtime
- `SUPABASE_PROJECT_ID` - Tu project ID de Supabase
- `SUPABASE_URL` - URL de tu proyecto Supabase
- `SUPABASE_KEY` - Tu API key de Supabase
- `ENVIRONMENT` - `production`
- `LOG_LEVEL` - `INFO`

### 4. Desplegar

Render desplegará automáticamente cuando hagas push a la rama principal.

## Estructura del Proyecto

```
CrearCarpetasSolicitudAcreditacion/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app principal
│   ├── models.py               # Modelos Pydantic
│   ├── config.py               # Configuración
│   ├── services/
│   │   ├── drive_service.py   # Servicio Google Drive
│   │   └── supabase_service.py # Servicio Supabase
│   ├── utils/
│   │   └── helpers.py         # Funciones auxiliares
│   └── routers/
│       └── carpetas.py        # Router de carpetas
├── tests/
│   └── test_main.py           # Tests
├── requirements.txt
├── runtime.txt                # Versión Python para Render
├── render.yaml                # Configuración Render
├── .env.example
├── .gitignore
└── README.md
```

## Endpoints

### `GET /`
Endpoint raíz con información de la API.

### `GET /health`
Health check endpoint.

### `POST /carpetas/crear`
Endpoint principal para crear carpetas.

**Request Body:**
- `codigo_proyecto` (string): Código en formato `MY-XXX-YYYY`
- `myma` (object): Datos MYMA con especialistas, conductores, vehículos
- `externo` (object): Datos externos con empresa, especialistas, conductores, vehículos

**Response:**
- `codigo_proyecto`: Código del proyecto
- `año_proyecto`: Año extraído del código
- `nombre_drive`: Nombre del Shared Drive
- `drive_id`: ID del Shared Drive
- `id_carpeta_final`: ID de la carpeta final de acreditación
- `json_final`: JSON con todos los datos y `id_folder` agregados
- `carpetas_externos`: Información de carpetas externos creadas
- `carpetas_myma`: Información de carpetas MYMA creadas
- `actualizaciones_supabase`: Resumen de actualizaciones en Supabase

## Manejo de Errores

La API retorna códigos HTTP apropiados:

- `200`: Éxito
- `400`: Error de validación o datos incorrectos
- `422`: Error de validación de Pydantic
- `500`: Error interno del servidor

## Logging

Los logs se configuran según `LOG_LEVEL` en `.env`. Los logs incluyen:
- Operaciones de Google Drive
- Actualizaciones de Supabase
- Errores y excepciones

## Seguridad

- **No commitear** archivos sensibles:
  - `.env`
  - `token.json`
- Usar variables de entorno en producción
- Configurar CORS apropiadamente en producción

## Troubleshooting

### Error: "No se encontró el Shared Drive"
- Verifica que el Shared Drive exista con el nombre `Proyectos YYYY`
- Verifica que la cuenta tenga acceso al Shared Drive

### Error: "Error navegando ruta del proyecto"
- Verifica que la estructura de carpetas exista:
  - `[Código Proyecto]` > `08 Terrenos` > `03 Acreditación y Arranque` > `01 Acreditación`

### Error: "Supabase no está configurado"
- Verifica que las variables `SUPABASE_URL` y `SUPABASE_KEY` estén configuradas
- La API continuará funcionando pero no actualizará Supabase

### Error: "No se encontro el archivo de token"
- Verifica que `GOOGLE_TOKEN_FILE` apunte a un archivo existente en el entorno de ejecucion
- Confirma permisos de lectura sobre el archivo

### Error: "Credenciales OAuth invalidas o sin refresh_token"
- Regenera `token.json` asegurando `access_type=offline` para obtener `refresh_token`
- Verifica que los `scopes` del token incluyan `https://www.googleapis.com/auth/drive`

### Error: "No se pudo refrescar el token OAuth"
- Reautoriza la cuenta y reemplaza `token.json` por uno vigente
- Revisa conectividad saliente a `https://oauth2.googleapis.com/token`

## Licencia

[Especificar licencia]

## Contacto

[Información de contacto]

