from django.http import JsonResponse

from .responses import error_payload


class ApiErrorResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith("/api/") and response.status_code == 404:
            return JsonResponse(
                error_payload(
                    message="Endpoint not found.",
                    errors={"path": request.path},
                ),
                status=404,
            )

        return response
