## Settings Approaches

### 1. Approach 

####  Django app settings

_settings variables addition_

myproject/settings.py
```
DEBUG = True
MONGO_URL = "mongodb://127.0.0.1:27017/infraon_db"
FILE_STORE = "local"
```

_currently, we are setting the module variables calling external api as_

```
env_settings = env.get_settings()
for each_setting in env_settings:
    ## setting AWS_KEY here
    setattr(sys.modules[__name__], each_setting["key"], each_setting["val"])
```

_using the settings variabels as_

```
from django.conf import settings

print(settings.MONGO_URL)
print(settings.AWS_KEY)
```

####  Celery/Consumers app settings

_settings variables addition_

settings/settings.py
```
DEBUG = True
MONGO_URL = "mongodb://127.0.0.1:27017/infraon_db"
FILE_STORE = "local"
```

_currently, we are setting the module variables calling external api as_

```
env_settings = env.get_settings()
for each_setting in env_settings:
    ## setting AWS_KEY here
    setattr(sys.modules[__name__], each_setting["key"], each_setting["val"])
```

_using the settings variabels as_

```
from settings import settings

print(settings.MONGO_URL)
print(settings.AWS_KEY)
```


### 2. Approach 

####  Common infraon settings module

_we can build a pydantic based setting module for all our components_
_this will be more moduler as per module or tool_

here is sample structure

```
infraon_api/
├── settings/
│   ├── __init__.py
│   ├── settings.py
│   ├── itsm.py
│   ├── nccm.py
│   └── oss.py
```

_itsm.py_
```
from pydantic_settings import BaseSettings


class SettingsITSM(BaseSettings):
    ITSM: bool

```

_settings.py_
```
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any, Dict
import requests
from .itsm import SettingITSM


class Settings(BaseSettings, SettingITSM):
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

"""
# init of setting module settings/__init__.py

settings = Settings()
print(settings.DEBUG)
print(settings.MONGO_URL)
"""

```


_using the settings variabels as_

```
from settings import settings

print(settings.MONGO_URL)
print(settings.AWS_KEY)
```


