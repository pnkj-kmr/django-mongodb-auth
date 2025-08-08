from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any, Dict
import requests

# from django.conf import settings
# from settings import settings


class Settings(BaseSettings):
    DEBUG: bool = False
    MONGO_URL: str = ""
    LOG_LEVEL: str = ""

    model_config = SettingsConfigDict(env_file=".env")

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, file_secret_settings
    ):
        return (
            cls.remote_settings_source,
            env_settings,  # still keep env vars
            init_settings,  # still allow init args
            file_secret_settings,  # for Docker secrets or mounted files
        )

    @classmethod
    def remote_settings_source(cls, settings: BaseSettings) -> Dict[str, Any]:
        try:
            response = requests.get("https://<env_endpoint>")
            response.raise_for_status()
            data = response.json()
            return data  # must be a flat dict {key: value}
        except Exception as e:
            print(f"Failed to load remote settings: {e}")
            return {}  # fallback if remote fetch fails


# Usage
settings = Settings()
print(settings.DEBUG)
print(settings.MONGO_URL)
