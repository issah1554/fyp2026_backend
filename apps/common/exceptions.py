from rest_framework import status
from rest_framework.views import exception_handler

from .responses import error_payload


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(response.data, dict) and "success" in response.data:
        return response

    message = "Request failed."
    errors = {}

    if isinstance(response.data, dict):
        if set(response.data.keys()) == {"detail"}:
            message = str(response.data["detail"])
        else:
            message = "Validation failed." if response.status_code == status.HTTP_400_BAD_REQUEST else message
            errors = response.data
    elif isinstance(response.data, list):
        message = "Validation failed." if response.status_code == status.HTTP_400_BAD_REQUEST else message
        errors = {"non_field_errors": response.data}

    response.data = error_payload(message=message, errors=errors)
    return response
