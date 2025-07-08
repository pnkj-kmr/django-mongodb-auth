from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.utils import timezone
from datetime import datetime
import jwt
from .models import User
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    RefreshTokenSerializer,
    LogoutSerializer,
)
from .jwt_utils import JWTUtils
import logging

logger = logging.getLogger("accounts")


class UserRegistrationView(APIView):
    """
    User registration endpoint.
    POST /api/auth/register/
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            try:
                user = serializer.save()

                # Generate tokens
                tokens = JWTUtils.generate_tokens(user)

                logger.info(f"New user registered: {user.email}")

                return Response(
                    {
                        "success": True,
                        "message": "User registered successfully",
                        "user": UserSerializer(user).data,
                        "tokens": {
                            "access": tokens["access"],
                            "refresh": tokens["refresh"],
                            "access_expires": tokens["access_expires"].isoformat(),
                            "refresh_expires": tokens["refresh_expires"].isoformat(),
                        },
                    },
                    status=status.HTTP_201_CREATED,
                )

            except Exception as e:
                logger.error(f"Registration error: {str(e)}")
                return Response(
                    {
                        "success": False,
                        "message": "Registration failed",
                        "error": str(e),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {
                "success": False,
                "message": "Validation failed",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class UserLoginView(APIView):
    """
    User login endpoint.
    POST /api/auth/login/
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)

        if serializer.is_valid():
            try:
                user = serializer.validated_data["user"]
                remember_me = serializer.validated_data.get("remember_me", False)

                # Update last login
                user.last_login = datetime.utcnow()
                user.save()

                # Generate tokens
                tokens = JWTUtils.generate_tokens(user)

                logger.info(f"User logged in: {user.email}")

                response_data = {
                    "success": True,
                    "message": "Login successful",
                    "user": UserSerializer(user).data,
                    "tokens": {
                        "access": tokens["access"],
                        "refresh": tokens["refresh"],
                        "access_expires": tokens["access_expires"].isoformat(),
                        "refresh_expires": tokens["refresh_expires"].isoformat(),
                    },
                }

                response = Response(response_data, status=status.HTTP_200_OK)

                # Set cookies if remember_me is True
                if remember_me:
                    response.set_cookie(
                        "refresh_token",
                        tokens["refresh"],
                        max_age=7 * 24 * 60 * 60,  # 7 days
                        httponly=True,
                        secure=not request.META.get("DEBUG", False),
                    )

                return response

            except Exception as e:
                logger.error(f"Login error: {str(e)}")
                return Response(
                    {"success": False, "message": "Login failed", "error": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {
                "success": False,
                "message": "Validation failed",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class TokenRefreshView(APIView):
    """
    Token refresh endpoint.
    POST /api/auth/token/refresh/
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)

        if serializer.is_valid():
            refresh_token = serializer.validated_data["refresh"]

            try:
                # Generate new access token
                new_tokens = JWTUtils.refresh_access_token(refresh_token)

                return Response(
                    {
                        "success": True,
                        "message": "Token refreshed successfully",
                        "tokens": {
                            "access": new_tokens["access"],
                            "expires": new_tokens["expires"].isoformat(),
                        },
                    },
                    status=status.HTTP_200_OK,
                )

            except jwt.InvalidTokenError as e:
                return Response(
                    {
                        "success": False,
                        "message": "Token refresh failed",
                        "error": str(e),
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            except Exception as e:
                logger.error(f"Token refresh error: {str(e)}")
                return Response(
                    {
                        "success": False,
                        "message": "Token refresh failed",
                        "error": str(e),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {
                "success": False,
                "message": "Validation failed",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class UserProfileView(APIView):
    """
    User profile endpoint.
    GET /api/auth/profile/ - Get user profile
    PATCH /api/auth/profile/ - Update user profile
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get current user profile."""
        try:
            # Get user from database (request.user might be cached)
            user = User.objects.get(id=request.user.id)

            return Response(
                {"success": True, "user": UserSerializer(user).data},
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def patch(self, request):
        """Update user profile."""
        try:
            user = User.objects.get(id=request.user.id)
            serializer = UserUpdateSerializer(
                data=request.data, partial=True, context={"user": user}
            )

            if serializer.is_valid():
                updated_user = serializer.update(user, serializer.validated_data)

                logger.info(f"Profile updated: {user.email}")

                return Response(
                    {
                        "success": True,
                        "message": "Profile updated successfully",
                        "user": UserSerializer(updated_user).data,
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {
                    "success": False,
                    "message": "Validation failed",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Profile update error: {str(e)}")
            return Response(
                {"success": False, "message": "Profile update failed", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChangePasswordView(APIView):
    """
    Change password endpoint.
    POST /api/auth/change-password/
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            user = User.objects.get(id=request.user.id)
            serializer = ChangePasswordSerializer(data=request.data)

            if serializer.is_valid():
                old_password = serializer.validated_data["old_password"]
                new_password = serializer.validated_data["new_password"]

                # Verify old password
                if not user.check_password(old_password):
                    return Response(
                        {"success": False, "message": "Current password is incorrect"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Set new password
                user.set_password(new_password)
                user.save()

                # Logout from all devices (invalidate all refresh tokens)
                JWTUtils.logout_user(user)

                logger.info(f"Password changed: {user.email}")

                return Response(
                    {
                        "success": True,
                        "message": "Password changed successfully. Please login again.",
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {
                    "success": False,
                    "message": "Validation failed",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": "Password change failed",
                    "error": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LogoutView(APIView):
    """
    User logout endpoint.
    POST /api/auth/logout/
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            user = User.objects.get(id=request.user.id)
            serializer = LogoutSerializer(data=request.data)

            if serializer.is_valid():
                refresh_token = serializer.validated_data.get("refresh")
                logout_all = serializer.validated_data.get("logout_all", False)

                if logout_all:
                    # Logout from all devices
                    JWTUtils.logout_user(user)
                    message = "Logged out from all devices successfully"
                else:
                    # Logout from current device only
                    if refresh_token:
                        JWTUtils.logout_user(user, refresh_token)
                    message = "Logged out successfully"

                logger.info(
                    f"User logged out: {user.email} (all devices: {logout_all})"
                )

                response = Response(
                    {"success": True, "message": message}, status=status.HTTP_200_OK
                )

                # Clear cookies
                response.delete_cookie("refresh_token")

                return response

            return Response(
                {
                    "success": False,
                    "message": "Validation failed",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response(
                {"success": False, "message": "Logout failed", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def auth_status(request):
    """
    Check authentication status.
    GET /api/auth/status/
    """
    if hasattr(request, "user") and request.user and hasattr(request.user, "id"):
        try:
            user = User.objects.get(id=request.user.id)
            return Response({"authenticated": True, "user": UserSerializer(user).data})
        except User.DoesNotExist:
            pass

    return Response({"authenticated": False, "user": None})
