import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "si", "sí"}


def _db_from_uri(uri: str) -> str:
    """Nombre de la base incluido en la URI (…mongodb.net/emergexia?…), si lo hay."""
    try:
        return urlparse(uri).path.strip("/")
    except ValueError:
        return ""


class Settings:
    # Spark
    spark_master: str = os.getenv("SPARK_MASTER", "local[*]")
    spark_app_name: str = os.getenv("SPARK_APP_NAME", "Emergexia")
    spark_ui_enabled: bool = _bool(os.getenv("SPARK_UI_ENABLED", "false"))
    spark_shuffle_partitions: str = os.getenv("SPARK_SHUFFLE_PARTITIONS", "4")
    spark_driver_memory: str = os.getenv("SPARK_DRIVER_MEMORY", "1g")
    spark_driver_host: str | None = os.getenv("SPARK_DRIVER_HOST") or None

    # MongoDB
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db: str = os.getenv("MONGO_DB") or _db_from_uri(os.getenv("MONGO_URI", "")) or "emergexia"
    mongo_timeout_ms: int = int(os.getenv("MONGO_TIMEOUT_MS", "8000"))
    # La primera vez, completar la flota con vehículos reales (API vPIC). Apagado por defecto:
    # los datos los captura la central.
    importar_flota_al_iniciar: bool = _bool(os.getenv("IMPORTAR_FLOTA_AL_INICIAR", "false"))

    # Carpeta de trabajo de Spark (opcional)
    data_dir: str = os.getenv("DATA_DIR", str(BASE_DIR / "data"))

    # Seguridad
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-cambiar")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    # Sin valor por defecto: si la base está vacía y no se define, no se crea ningún
    # administrador (antes era "admin123", una contraseña que cualquiera podría adivinar).
    admin_password: str = os.getenv("ADMIN_PASSWORD", "")
    admin_name: str = os.getenv("ADMIN_NAME", "Yessica López")

    # Carpeta con las pantallas ya construidas (npm run build). En Docker/Render: /app/static.
    frontend_dir: str = os.getenv("FRONTEND_DIR", str(BASE_DIR / "static"))

    cors_origins: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
    ]


settings = Settings()
