from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TOLLGATE_", env_file=".env", extra="ignore")
    database_url: str = "sqlite+aiosqlite:///./tollgate.db"
    redis_url: str = ""
    master_key: str = ""
    admin_email: str = "admin@tollgate.local"
    admin_password: str = ""
    demo: bool = False
    enable_mock_provider: bool = True
    cookie_secure: bool = False
    allowed_origin: str = "http://localhost:3187"
    port: int = 8187
    max_concurrent_requests: int = Field(default=100, ge=1, le=10000)
    bootstrap_file: str = ""
    presidio_url: str = ""
    kms_key_id: str = ""

    def validate_secrets(self):
        if not self.demo and (len(self.admin_password) < 12 or not self.master_key):
            raise RuntimeError(
                "Set a 12+ character admin password and base64 32-byte master key, or enable demo mode"
            )
        if self.kms_key_id or self.presidio_url:
            raise RuntimeError("KMS and Presidio are not implemented; remove their settings")
