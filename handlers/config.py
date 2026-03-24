from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    max_bot_token: SecretStr = Field(validation_alias=AliasChoices("MAX_BOT_TOKEN", "BOT_TOKEN", "max_bot_token", "bot_token"))
    db_host: str = Field(validation_alias=AliasChoices("DB_HOST", "db_host"))
    db_port: int = Field(validation_alias=AliasChoices("DB_PORT", "db_port"))
    db_name: str = Field(validation_alias=AliasChoices("DB_NAME", "db_name"))
    db_user: str = Field(validation_alias=AliasChoices("DB_USER", "db_user"))
    db_password: SecretStr = Field(validation_alias=AliasChoices("DB_PASSWORD", "db_password"))
    chanel_id: SecretStr = Field(validation_alias=AliasChoices("CHANEL_ID", "chanel_id"))
    client_id: SecretStr = Field(validation_alias=AliasChoices("CLIENT_ID", "client_id"))
    yandex_disk_token: SecretStr = Field(validation_alias=AliasChoices("YANDEX_DISK_TOKEN", "yandex_disk_token"))

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def db_connection(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password.get_secret_value()}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


config = Settings()
