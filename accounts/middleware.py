# from django.utils.deprecation import MiddlewareMixin
# from django.http import JsonResponse
# from django.conf import settings
# from .jwt_utils import EnhancedJWTUtils
# import json


# class TokenRefreshMiddleware(MiddlewareMixin):
#     """Middleware to automatically refresh tokens in grace period."""

#     def process_response(self, request, response):
#         """Add refresh hint headers if token needs refresh."""
#         if hasattr(request, "token_needs_refresh") and request.token_needs_refresh:
#             # Add header suggesting client should refresh token
#             response["X-Token-Refresh-Suggested"] = "true"
#             response["X-Refresh-JTI"] = request.refresh_jti

#             # Optionally auto-refresh if configured
#             if getattr(settings, "JWT_AUTO_REFRESH_IN_RESPONSE", False):
#                 try:
#                     refresh_jti = request.refresh_jti
#                     # Find refresh token (this would need to be stored somewhere accessible)
#                     # For demo purposes, we'll skip the actual refresh here
#                     pass
#                 except Exception:
#                     pass

#         return response
