from rest_framework import status
from rest_framework.views import exception_handler

from .responses import error_payload

INVALID_CREDENTIALS_DETAIL = "No active account found with the given credentials"


def first_error_message(errors):
    if isinstance(errors, dict):
        for value in errors.values():
            message = first_error_message(value)
            if message:
                return message
    elif isinstance(errors, list):
        for value in errors:
            message = first_error_message(value)
            if message:
                return message
    elif errors:
        return str(errors)
    return ""


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
            if message == INVALID_CREDENTIALS_DETAIL:
                message = "Invalid credentials"
        else:
            errors = response.data
            if response.status_code == status.HTTP_400_BAD_REQUEST:
                message = first_error_message(errors) or "Validation failed."
    elif isinstance(response.data, list):
        errors = {"non_field_errors": response.data}
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            message = first_error_message(errors) or "Validation failed."

    response.data = error_payload(message=message, errors=errors)
    return response
