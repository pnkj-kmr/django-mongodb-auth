from pydantic_settings import BaseSettings
from typing import Optional


class SettingsNCCM(BaseSettings):
    NCCM: Optional[bool] = False
