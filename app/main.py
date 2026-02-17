"""Aplicación FastAPI principal."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import carpetas
from app.config import ENV_FILE_PATH, settings

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info(
    "Config carga inicial: SUPABASE_URL=%s SUPABASE_KEY=%s ENV_FILE=%s exists=%s",
    bool(settings.supabase_url),
    bool(settings.supabase_key),
    ENV_FILE_PATH,
    ENV_FILE_PATH.exists(),
)

app = FastAPI(
    title="API Crear Carpetas Solicitud Acreditación",
    description="API para crear carpetas en Google Drive y actualizar Supabase",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(carpetas.router)


@app.get("/")
async def root():
    """Endpoint raíz."""
    return {
        "message": "API Crear Carpetas Solicitud Acreditación",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Endpoint de health check."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

