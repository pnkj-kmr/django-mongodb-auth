from pydantic_settings import BaseSettings
from typing import Optional


class SettingsITSM(BaseSettings):
    ITSM: Optional[bool] = False
