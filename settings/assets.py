from pydantic_settings import BaseSettings
from typing import Optional


class SettingsASSET(BaseSettings):
    ASSET: Optional[bool] = False
