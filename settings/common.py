import os
from pathlib import Path
from datetime import timedelta
from decouple import config
import mongoengine

BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "*"] if DEBUG else []

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",  # Keep for admin panel
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "rest_framework",
    "corsheaders",
    # Local apps
    "accounts",  # Our MongoDB auth app
    "api",  # Our API app
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "myproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "myproject.wsgi.application"

# Database - SQLite for Django admin only
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "admin.sqlite3",  # Keep admin DB separate
    }
}

# MongoDB Configuration with MongoEngine
MONGODB_SETTINGS = {
    "db": config("DB_NAME", default="django_mongodb_auth"),
    "host": config("DB_HOST", default="localhost"),
    "port": int(config("DB_PORT", default=27017)),
    "username": config("DB_USER", default=""),
    "password": config("DB_PASSWORD", default=""),
    "authentication_source": config("DB_AUTH_SOURCE", default="admin"),
    "connect": False,  # Important for avoiding connection issues
}

# Connect to MongoDB
try:
    mongoengine.connect(**MONGODB_SETTINGS)
    print("✅ MongoDB connected successfully")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")

# Method 1: Using individual config values (more secure)
REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = config("REDIS_PORT", default=6379, cast=int)
REDIS_PASSWORD = config("REDIS_PASSWORD", default="")
REDIS_DB = config("REDIS_DB", default=0, cast=int)

# With authentication
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "retry_on_timeout": True,
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
                "password": REDIS_PASSWORD,
            },
        },
    }
}

# Redis connection test
try:
    from django.core.cache import cache

    cache.set("test_key", "test_value", 10)
    if cache.get("test_key") == "test_value":
        print("✅ Redis connected successfully")
        cache.delete("test_key")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.JWTAuthentication",  # Our custom JWT auth
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "accounts.exceptions.custom_exception_handler",
}

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "accounts.authentication.MongoEngineBackend",  # Our MongoDB backend
    "django.contrib.auth.backends.ModelBackend",  # Keep for admin
]

# JWT Configuration
JWT_SETTINGS = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),  # Short-lived for security
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),  # Longer-lived
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),  # Optional: sliding session
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    # Auto-refresh settings
    "ROTATE_REFRESH_TOKENS": True,  # Generate new refresh token on use
    "BLACKLIST_AFTER_ROTATION": True,  # Invalidate old refresh token
    "UPDATE_LAST_LOGIN": True,  # Track last activity
    # Grace period settings
    "ACCESS_TOKEN_GRACE_PERIOD": timedelta(minutes=2),  # Allow expired tokens briefly
    "REFRESH_TOKEN_GRACE_PERIOD": timedelta(hours=1),  # Grace for refresh
}

# CORS settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Only in development

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO" if DEBUG else "WARNING",
    },
    "loggers": {
        "accounts": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}
