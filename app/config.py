from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE_PATH = PROJECT_ROOT / ".env"

# Carga .env usando ruta absoluta para evitar problemas de CWD en VM/servicios.
load_dotenv(dotenv_path=ENV_FILE_PATH)


class Settings(BaseSettings):
    """Configuración de la aplicación desde variables de entorno."""
    
    # Google Drive
    google_token_file: str = "token.json"
    
    # Supabase
    supabase_project_id: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    
    # Application
    environment: str = "development"
    log_level: str = "INFO"
    
    class Config:
        env_file = str(ENV_FILE_PATH)
        case_sensitive = False
        extra = "ignore"


settings = Settings()

