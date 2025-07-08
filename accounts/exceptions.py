from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger("accounts")


def custom_exception_handler(exc, context):
    """
    Custom exception handler for better error responses.
    """
    response = exception_handler(exc, context)

    if response is not None:
        custom_response_data = {
            "error": True,
            "message": "An error occurred",
            "details": response.data,
            "status_code": response.status_code,
        }

        # Customize message based on status code
        if response.status_code == 401:
            custom_response_data["message"] = "Authentication required"
        elif response.status_code == 403:
            custom_response_data["message"] = "Permission denied"
        elif response.status_code == 404:
            custom_response_data["message"] = "Resource not found"
        elif response.status_code == 400:
            custom_response_data["message"] = "Bad request"
        elif response.status_code >= 500:
            custom_response_data["message"] = "Internal server error"
            logger.error(f"Server error: {exc}", exc_info=True)

        response.data = custom_response_data

    return response
