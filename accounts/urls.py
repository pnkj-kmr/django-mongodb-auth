from django.urls import path
from .views import (
    UserRegistrationView,
    UserLoginView,
    TokenRefreshView,
    UserProfileView,
    ChangePasswordView,
    LogoutView,
    auth_status,
)

urlpatterns = [  # Authentication endpoints
    path("register/", UserRegistrationView.as_view(), name="user-register"),
    path("login/", UserLoginView.as_view(), name="user-login"),
    path("logout/", LogoutView.as_view(), name="user-logout"),
    # Token management
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # User profile
    path("profile/", UserProfileView.as_view(), name="user-profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    # Utility endpoints
    path("status/", auth_status, name="auth-status"),
]
