import jwt
import uuid
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from .models import User


class JWTUtils:
    """
    Custom JWT utility class for token generation and validation.
    Uses PyJWT and Redis for token management.
    """

    @staticmethod
    def generate_tokens(user):
        """
        Generate access and refresh tokens for a user.

        Args:
            user: User instance

        Returns:
            dict: Contains 'access', 'refresh', and token metadata
        """
        now = datetime.utcnow()

        # Generate unique JTI (JWT ID) for both tokens
        access_jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())

        # Access token payload
        access_payload = {
            "user_id": str(user.id),
            "email": user.email,
            "username": user.username,
            "token_type": "access",
            "iat": now,
            "exp": now + settings.JWT_SETTINGS["ACCESS_TOKEN_LIFETIME"],
            "jti": access_jti,
        }

        # Refresh token payload
        refresh_payload = {
            "user_id": str(user.id),
            "email": user.email,
            "token_type": "refresh",
            "iat": now,
            "exp": now + settings.JWT_SETTINGS["REFRESH_TOKEN_LIFETIME"],
            "jti": refresh_jti,
        }

        # Generate tokens
        access_token = jwt.encode(
            access_payload,
            settings.JWT_SETTINGS["SIGNING_KEY"],
            algorithm=settings.JWT_SETTINGS["ALGORITHM"],
        )

        refresh_token = jwt.encode(
            refresh_payload,
            settings.JWT_SETTINGS["SIGNING_KEY"],
            algorithm=settings.JWT_SETTINGS["ALGORITHM"],
        )

        # Store refresh token in user's active tokens
        user.add_refresh_token(refresh_jti)

        # Cache user data for quick access
        cache.set(
            f"user:{user.id}",
            {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "is_active": user.is_active,
            },
            timeout=int(
                settings.JWT_SETTINGS["REFRESH_TOKEN_LIFETIME"].total_seconds()
            ),
        )

        return {
            "access": access_token,
            "refresh": refresh_token,
            "access_expires": access_payload["exp"],
            "refresh_expires": refresh_payload["exp"],
            "user_id": str(user.id),
        }

    @staticmethod
    def decode_token(token, verify_exp=True):
        """
        Decode and validate a JWT token.

        Args:
            token: JWT token string
            verify_exp: Whether to verify token expiration

        Returns:
            dict: Token payload if valid

        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SETTINGS["SIGNING_KEY"],
                algorithms=[settings.JWT_SETTINGS["ALGORITHM"]],
                options={"verify_exp": verify_exp},
            )

            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti and cache.get(f"blacklist:{jti}"):
                raise jwt.InvalidTokenError("Token is blacklisted")

            return payload

        except jwt.InvalidTokenError:
            raise

    @staticmethod
    def refresh_access_token(refresh_token):
        """
        Generate new access token from refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            dict: New access token data

        Raises:
            jwt.InvalidTokenError: If refresh token is invalid
        """
        try:
            # Decode refresh token
            payload = JWTUtils.decode_token(refresh_token)

            if payload.get("token_type") != "refresh":
                raise jwt.InvalidTokenError("Invalid token type")

            # Get user
            user_id = payload.get("user_id")
            user = User.objects.get(id=user_id)

            if not user.is_active:
                raise jwt.InvalidTokenError("User account is disabled")

            # Check if refresh token is in user's active tokens
            refresh_jti = payload.get("jti")
            if refresh_jti not in user.refresh_tokens:
                raise jwt.InvalidTokenError(
                    "Refresh token not found in user's active tokens"
                )

            # Generate new access token
            now = datetime.utcnow()
            access_jti = str(uuid.uuid4())

            access_payload = {
                "user_id": str(user.id),
                "email": user.email,
                "username": user.username,
                "token_type": "access",
                "iat": now,
                "exp": now + settings.JWT_SETTINGS["ACCESS_TOKEN_LIFETIME"],
                "jti": access_jti,
            }

            access_token = jwt.encode(
                access_payload,
                settings.JWT_SETTINGS["SIGNING_KEY"],
                algorithm=settings.JWT_SETTINGS["ALGORITHM"],
            )

            return {
                "access": access_token,
                "expires": access_payload["exp"],
                "user_id": str(user.id),
            }

        except User.DoesNotExist:
            raise jwt.InvalidTokenError("User not found")
        except Exception as e:
            raise jwt.InvalidTokenError(f"Token refresh failed: {str(e)}")

    @staticmethod
    def blacklist_token(token):
        """
        Blacklist a token (add to Redis blacklist).

        Args:
            token: JWT token to blacklist

        Returns:
            bool: True if successfully blacklisted
        """
        try:
            payload = JWTUtils.decode_token(token, verify_exp=False)
            jti = payload.get("jti")
            exp = payload.get("exp")

            if jti and exp:
                # Calculate TTL (time until expiration)
                exp_datetime = datetime.fromtimestamp(exp)
                ttl = int((exp_datetime - datetime.utcnow()).total_seconds())

                if ttl > 0:
                    # Add to blacklist with TTL
                    cache.set(f"blacklist:{jti}", "1", timeout=ttl)
                    return True

            return False

        except Exception:
            return False

    @staticmethod
    def logout_user(user, refresh_token=None):
        """
        Logout user by blacklisting tokens.

        Args:
            user: User instance
            refresh_token: Specific refresh token to logout (optional)

        Returns:
            bool: True if logout successful
        """
        try:
            if refresh_token:
                # Logout from specific device
                payload = JWTUtils.decode_token(refresh_token, verify_exp=False)
                jti = payload.get("jti")

                # Remove from user's active tokens
                user.remove_refresh_token(jti)

                # Blacklist the refresh token
                JWTUtils.blacklist_token(refresh_token)
            else:
                # Logout from all devices
                user.clear_refresh_tokens()

            # Clear user cache
            cache.delete(f"user:{user.id}")

            return True

        except Exception:
            return False


# class EnhancedJWTUtils:
#     """Enhanced JWT utilities with auto-refresh and timeout handling."""

#     @staticmethod
#     def generate_tokens(user, device_id=None):
#         """
#         Generate access and refresh tokens with enhanced metadata.

#         Args:
#             user: User instance
#             device_id: Optional device identifier for multi-device support
#         """
#         now = datetime.utcnow()

#         # Generate unique JTIs
#         access_jti = str(uuid.uuid4())
#         refresh_jti = str(uuid.uuid4())

#         # Device tracking for multi-device logout
#         device_id = device_id or str(uuid.uuid4())

#         # Access token payload
#         access_payload = {
#             "user_id": str(user.id),
#             "email": user.email,
#             "username": user.username,
#             "token_type": "access",
#             "device_id": device_id,
#             "iat": now,
#             "exp": now + settings.JWT_SETTINGS["ACCESS_TOKEN_LIFETIME"],
#             "jti": access_jti,
#             "refresh_jti": refresh_jti,  # Link to refresh token
#         }

#         # Refresh token payload
#         refresh_payload = {
#             "user_id": str(user.id),
#             "email": user.email,
#             "token_type": "refresh",
#             "device_id": device_id,
#             "iat": now,
#             "exp": now + settings.JWT_SETTINGS["REFRESH_TOKEN_LIFETIME"],
#             "jti": refresh_jti,
#             "access_jti": access_jti,  # Link to access token
#         }

#         # Generate tokens
#         access_token = jwt.encode(
#             access_payload,
#             settings.JWT_SETTINGS["SIGNING_KEY"],
#             algorithm=settings.JWT_SETTINGS["ALGORITHM"],
#         )

#         refresh_token = jwt.encode(
#             refresh_payload,
#             settings.JWT_SETTINGS["SIGNING_KEY"],
#             algorithm=settings.JWT_SETTINGS["ALGORITHM"],
#         )

#         # Store refresh token metadata in Redis
#         refresh_key = f"refresh_token:{refresh_jti}"
#         cache.set(
#             refresh_key,
#             {
#                 "user_id": str(user.id),
#                 "device_id": device_id,
#                 "created_at": now.isoformat(),
#                 "last_used": now.isoformat(),
#             },
#             timeout=int(
#                 settings.JWT_SETTINGS["REFRESH_TOKEN_LIFETIME"].total_seconds()
#             ),
#         )

#         # Store user session info
#         user.add_refresh_token(refresh_jti)

#         return {
#             "access": access_token,
#             "refresh": refresh_token,
#             "access_expires": access_payload["exp"],
#             "refresh_expires": refresh_payload["exp"],
#             "device_id": device_id,
#             "expires_in": int(
#                 settings.JWT_SETTINGS["ACCESS_TOKEN_LIFETIME"].total_seconds()
#             ),
#         }

#     @staticmethod
#     def decode_token(token, verify_exp=True, allow_grace_period=False):
#         """
#         Decode token with optional grace period for expired tokens.

#         Args:
#             token: JWT token string
#             verify_exp: Whether to verify expiration
#             allow_grace_period: Allow recently expired tokens
#         """
#         try:
#             payload = jwt.decode(
#                 token,
#                 settings.JWT_SETTINGS["SIGNING_KEY"],
#                 algorithms=[settings.JWT_SETTINGS["ALGORITHM"]],
#                 options={"verify_exp": verify_exp},
#             )

#             # Check if token is blacklisted
#             jti = payload.get("jti")
#             if jti and cache.get(f"blacklist:{jti}"):
#                 raise jwt.InvalidTokenError("Token is blacklisted")

#             return payload

#         except jwt.ExpiredSignatureError:
#             if allow_grace_period:
#                 # Try to decode without expiration check
#                 try:
#                     payload = jwt.decode(
#                         token,
#                         settings.JWT_SETTINGS["SIGNING_KEY"],
#                         algorithms=[settings.JWT_SETTINGS["ALGORITHM"]],
#                         options={"verify_exp": False},
#                     )

#                     # Check if within grace period
#                     exp = datetime.fromtimestamp(payload["exp"])
#                     now = datetime.utcnow()
#                     grace_period = settings.JWT_SETTINGS.get(
#                         "ACCESS_TOKEN_GRACE_PERIOD", timedelta(minutes=2)
#                     )

#                     if now - exp <= grace_period:
#                         payload["_grace_period"] = True
#                         return payload

#                 except jwt.InvalidTokenError:
#                     pass

#             raise jwt.ExpiredSignatureError("Token has expired")

#         except jwt.InvalidTokenError:
#             raise

#     @staticmethod
#     def refresh_access_token(refresh_token, auto_rotate=None):
#         """
#         Generate new access token from refresh token with rotation support.

#         Args:
#             refresh_token: Valid refresh token
#             auto_rotate: Whether to rotate refresh token (default from settings)
#         """
#         if auto_rotate is None:
#             auto_rotate = settings.JWT_SETTINGS.get("ROTATE_REFRESH_TOKENS", True)

#         try:
#             # Decode refresh token
#             payload = EnhancedJWTUtils.decode_token(refresh_token)

#             if payload.get("token_type") != "refresh":
#                 raise jwt.InvalidTokenError("Invalid token type")

#             user_id = payload.get("user_id")
#             refresh_jti = payload.get("jti")
#             device_id = payload.get("device_id")

#             # Verify refresh token exists in Redis
#             refresh_key = f"refresh_token:{refresh_jti}"
#             token_metadata = cache.get(refresh_key)
#             if not token_metadata:
#                 raise jwt.InvalidTokenError("Refresh token not found or expired")

#             # Get user
#             user = User.objects.get(id=user_id)
#             if not user.is_active:
#                 raise jwt.InvalidTokenError("User account is disabled")

#             # Check if refresh token is in user's active tokens
#             if refresh_jti not in user.refresh_tokens:
#                 raise jwt.InvalidTokenError(
#                     "Refresh token not found in user's active tokens"
#                 )

#             # Update last used timestamp
#             token_metadata["last_used"] = datetime.utcnow().isoformat()
#             cache.set(
#                 refresh_key,
#                 token_metadata,
#                 timeout=int(
#                     settings.JWT_SETTINGS["REFRESH_TOKEN_LIFETIME"].total_seconds()
#                 ),
#             )

#             if auto_rotate:
#                 # Generate completely new token pair
#                 new_tokens = EnhancedJWTUtils.generate_tokens(user, device_id)

#                 # Blacklist old refresh token if configured
#                 if settings.JWT_SETTINGS.get("BLACKLIST_AFTER_ROTATION", True):
#                     EnhancedJWTUtils.blacklist_token(refresh_token)
#                     user.remove_refresh_token(refresh_jti)

#                 return new_tokens
#             else:
#                 # Generate only new access token
#                 now = datetime.utcnow()
#                 access_jti = str(uuid.uuid4())

#                 access_payload = {
#                     "user_id": str(user.id),
#                     "email": user.email,
#                     "username": user.username,
#                     "token_type": "access",
#                     "device_id": device_id,
#                     "iat": now,
#                     "exp": now + settings.JWT_SETTINGS["ACCESS_TOKEN_LIFETIME"],
#                     "jti": access_jti,
#                     "refresh_jti": refresh_jti,
#                 }

#                 access_token = jwt.encode(
#                     access_payload,
#                     settings.JWT_SETTINGS["SIGNING_KEY"],
#                     algorithm=settings.JWT_SETTINGS["ALGORITHM"],
#                 )

#                 return {
#                     "access": access_token,
#                     "refresh": refresh_token,  # Same refresh token
#                     "access_expires": access_payload["exp"],
#                     "expires_in": int(
#                         settings.JWT_SETTINGS["ACCESS_TOKEN_LIFETIME"].total_seconds()
#                     ),
#                 }

#         except User.DoesNotExist:
#             raise jwt.InvalidTokenError("User not found")
#         except Exception as e:
#             raise jwt.InvalidTokenError(f"Token refresh failed: {str(e)}")

#     @staticmethod
#     def check_token_expiry(token):
#         """
#         Check token expiry status without raising exceptions.

#         Returns:
#             dict: {
#                 'valid': bool,
#                 'expired': bool,
#                 'expires_in': int (seconds),
#                 'grace_period': bool
#             }
#         """
#         try:
#             payload = jwt.decode(
#                 token,
#                 settings.JWT_SETTINGS["SIGNING_KEY"],
#                 algorithms=[settings.JWT_SETTINGS["ALGORITHM"]],
#                 options={"verify_exp": False},
#             )

#             exp = datetime.fromtimestamp(payload["exp"])
#             now = datetime.utcnow()
#             expires_in = int((exp - now).total_seconds())

#             if expires_in > 0:
#                 return {
#                     "valid": True,
#                     "expired": False,
#                     "expires_in": expires_in,
#                     "grace_period": False,
#                 }
#             else:
#                 # Check grace period
#                 grace_period = settings.JWT_SETTINGS.get(
#                     "ACCESS_TOKEN_GRACE_PERIOD", timedelta(minutes=2)
#                 )
#                 in_grace = abs(expires_in) <= grace_period.total_seconds()

#                 return {
#                     "valid": in_grace,
#                     "expired": True,
#                     "expires_in": expires_in,
#                     "grace_period": in_grace,
#                 }

#         except jwt.InvalidTokenError:
#             return {
#                 "valid": False,
#                 "expired": True,
#                 "expires_in": 0,
#                 "grace_period": False,
#             }
