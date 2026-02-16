from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


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
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()

