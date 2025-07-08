from django.contrib.auth.backends import BaseBackend
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.core.cache import cache
import jwt
from .models import User
from .jwt_utils import JWTUtils
# from .jwt_utils import EnhancedJWTUtils


class MongoEngineBackend(BaseBackend):
    """
    Custom authentication backend for MongoEngine User model.
    Used for Django admin and other Django auth needs.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Authenticate user with email and password."""
        email = kwargs.get("email", username)

        if email and password:
            try:
                user = User.objects.get(email=email)
                if user.check_password(password) and user.is_active:
                    # Update last login
                    from datetime import datetime

                    user.last_login = datetime.utcnow()
                    user.save()
                    return user
            except User.DoesNotExist:
                pass
        return None

    def get_user(self, user_id):
        """Get user by ID."""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None


class JWTAuthentication(BaseAuthentication):
    """
    Custom JWT authentication for Django REST Framework.
    Handles JWT token validation and user retrieval.
    """

    def authenticate(self, request):
        """
        Authenticate user from JWT token in Authorization header.

        Returns:
            tuple: (user, token) if authentication successful, None otherwise
        """
        header = self.get_authorization_header(request)

        if not header:
            return None

        token = self.get_token_from_header(header)
        if not token:
            return None

        return self.authenticate_credentials(token)

    def get_authorization_header(self, request):
        """Get authorization header from request."""
        return request.META.get("HTTP_AUTHORIZATION", b"")

    def get_token_from_header(self, header):
        """Extract token from authorization header."""
        if isinstance(header, str):
            header = header.encode("utf-8")

        parts = header.split()

        if len(parts) != 2:
            return None

        auth_type, token = parts

        if auth_type.lower() != b"bearer":
            return None

        try:
            return token.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def authenticate_credentials(self, token):
        """
        Authenticate user from JWT token.

        Args:
            token: JWT token string

        Returns:
            tuple: (user, token)

        Raises:
            AuthenticationFailed: If authentication fails
        """
        try:
            # Decode and validate token
            payload = JWTUtils.decode_token(token)

            # Check token type
            if payload.get("token_type") != "access":
                raise AuthenticationFailed("Invalid token type")

            user_id = payload.get("user_id")
            if not user_id:
                raise AuthenticationFailed("Invalid token payload")

            # Try to get user from cache first
            cached_user = cache.get(f"user:{user_id}")
            if cached_user and cached_user.get("is_active"):
                # Create a minimal user object for the request
                user = self.get_cached_user(cached_user)
            else:
                # Get user from database
                user = User.objects.get(id=user_id)
                if not user.is_active:
                    raise AuthenticationFailed("User account is disabled")

            return (user, token)

        except jwt.InvalidTokenError as e:
            raise AuthenticationFailed(f"Invalid token: {str(e)}")
        except User.DoesNotExist:
            raise AuthenticationFailed("User not found")
        except Exception as e:
            raise AuthenticationFailed(f"Authentication failed: {str(e)}")

    def get_cached_user(self, cached_user):
        """Create user object from cached data."""

        class CachedUser:
            def __init__(self, data):
                self.id = data["id"]
                self.email = data["email"]
                self.username = data["username"]
                self.is_active = data["is_active"]
                self.is_authenticated = True
                self.is_anonymous = False

        return CachedUser(cached_user)

    def authenticate_header(self, request):
        """Return authentication header for 401 responses."""
        return "Bearer"


# class EnhancedJWTAuthentication(BaseAuthentication):
#     """Enhanced JWT authentication with grace period and auto-refresh hints."""

#     def authenticate(self, request):
#         """Authenticate with grace period support."""
#         header = self.get_authorization_header(request)
#         if not header:
#             return None

#         token = self.get_token_from_header(header)
#         if not token:
#             return None

#         return self.authenticate_credentials(token, request)

#     def authenticate_credentials(self, token, request):
#         """Authenticate with grace period and refresh hints."""
#         try:
#             # First try normal validation
#             try:
#                 payload = EnhancedJWTUtils.decode_token(token)
#                 grace_period = False
#             except jwt.ExpiredSignatureError:
#                 # Try with grace period
#                 payload = EnhancedJWTUtils.decode_token(token, allow_grace_period=True)
#                 grace_period = payload.get("_grace_period", False)

#                 if not grace_period:
#                     raise jwt.ExpiredSignatureError("Token expired beyond grace period")

#             # Validate token type
#             if payload.get("token_type") != "access":
#                 raise AuthenticationFailed("Invalid token type")

#             user_id = payload.get("user_id")
#             if not user_id:
#                 raise AuthenticationFailed("Invalid token payload")

#             # Get user (with caching)
#             cached_user = cache.get(f"user:{user_id}")
#             if cached_user and cached_user.get("is_active"):
#                 user = self.create_user_from_cache(cached_user)
#             else:
#                 user = User.objects.get(id=user_id)
#                 if not user.is_active:
#                     raise AuthenticationFailed("User account is disabled")

#             # Add refresh hint to request if in grace period
#             if grace_period:
#                 request.token_needs_refresh = True
#                 request.refresh_jti = payload.get("refresh_jti")

#             return (user, token)

#         except jwt.InvalidTokenError as e:
#             raise AuthenticationFailed(f"Invalid token: {str(e)}")
#         except User.DoesNotExist:
#             raise AuthenticationFailed("User not found")
#         except Exception as e:
#             raise AuthenticationFailed(f"Authentication failed: {str(e)}")
