from pydantic_settings import BaseSettings
from typing import Optional


class SettingsOSS(BaseSettings):
    TELECOM_OSS: Optional[bool] = True
