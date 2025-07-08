from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings


def health_check(request):
    """Simple health check endpoint"""
    return JsonResponse(
        {
            "status": "healthy",
            "message": "Django + MongoDB + Redis API is running",
            "debug": settings.DEBUG if "settings" in globals() else False,
        }
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/v1/", include("api.urls")),
]
