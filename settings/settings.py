from .itsm import SettingsITSM
from .nccm import SettingsNCCM
from .assets import SettingsASSET
from .oss import SettingsOSS

# #
# # Django specific urls
# #
# DEBUG: bool = False
# MEDIA_URL = None
# ADMIN_URL = None
# X_FRAME_OPTIONS = None
# CORS_ALLOWED_LIST = None
# CELERY_BROKER_URL = None
# CELERY_RESULTS_BACKEND = None


class Settings(SettingsITSM, SettingsOSS, SettingsASSET, SettingsNCCM):
    MONGO_URL: str = ""


settings = Settings(MONGO_URL="mongodb://127.0.0.1/abc", NCCM=True)
print("setting variables--> ", settings.ITSM)
print("setting variables--> ", settings.TELECOM_OSS)
print("setting variables--> ", settings.NCCM)
print("setting variables--> ", settings.MONGO_URL)
