from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt


@method_decorator(csrf_exempt, name="dispatch")
class UssdMenuView(View):
    http_method_names = ["get", "post"]

    def _get_value(self, request, key):
        return (
            request.POST.get(key)
            or request.GET.get(key)
            or request.headers.get(key)
            or request.headers.get(key.lower())
            or ""
        ).strip()

    def post(self, request, *args, **kwargs):
        session_id = self._get_value(request, "sessionId")
        service_code = self._get_value(request, "serviceCode")
        phone_number = self._get_value(request, "phoneNumber")
        text = self._get_value(request, "text")

        # Keep sandbox callbacks alive even if some fields are omitted or sent differently.
        _ = session_id, service_code, phone_number

        if text == "":
            response_text = (
                "CON What would you want to check \n"
                "1. My Account \n"
                "2. My phone number"
            )
        elif text == "1":
            response_text = (
                "CON Choose account information you want to view \n"
                "1. Account number"
            )
        elif text == "2":
            response_text = f"END Your phone number is {phone_number or 'unknown'}"
        elif text == "1*1":
            response_text = "END Your account number is ACC1001"
        else:
            response_text = "END Invalid choice. Please try again."

        return HttpResponse(response_text, content_type="text/plain")

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)
