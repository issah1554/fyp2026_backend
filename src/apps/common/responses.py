from datetime import UTC

from django.utils import timezone
from rest_framework.response import Response


def response_timestamp():
    return timezone.now().astimezone(UTC).isoformat().replace("+00:00", "Z")


def success_payload(data=None, meta=None):
    return {
        "success": True,
        "data": {} if data is None else data,
        "meta": {} if meta is None else meta,
        "timestamp": response_timestamp(),
    }


def mutation_payload(message, data=None, meta=None):
    return {
        "success": True,
        "message": message,
        "data": {} if data is None else data,
        "meta": {} if meta is None else meta,
        "timestamp": response_timestamp(),
    }


def error_payload(message, errors=None, meta=None):
    return {
        "success": False,
        "message": message,
        "errors": {} if errors is None else errors,
        "meta": {} if meta is None else meta,
        "timestamp": response_timestamp(),
    }


def success_response(data=None, meta=None, status_code=200):
    return Response(success_payload(data=data, meta=meta), status=status_code)


def collection_meta(pagination=None, filters=None, sorting=None, search=""):
    return {
        "pagination": {} if pagination is None else pagination,
        "filters": {} if filters is None else filters,
        "sorting": {} if sorting is None else sorting,
        "search": search,
    }


def collection_response(data=None, meta=None, status_code=200):
    return success_response(
        data=[] if data is None else data,
        meta=collection_meta() if meta is None else meta,
        status_code=status_code,
    )


def mutation_response(message, data=None, meta=None, status_code=200):
    return Response(mutation_payload(message=message, data=data, meta=meta), status=status_code)


def error_response(message, errors=None, meta=None, status_code=400):
    return Response(error_payload(message=message, errors=errors, meta=meta), status=status_code)
