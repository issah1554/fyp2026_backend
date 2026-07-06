from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt


@method_decorator(csrf_exempt, name="dispatch")
class UssdMenuView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        session_id = request.POST.get("sessionId", "").strip()
        service_code = request.POST.get("serviceCode", "").strip()
        phone_number = request.POST.get("phoneNumber", "").strip()
        text = request.POST.get("text", "").strip()

        if not session_id or not service_code or not phone_number:
            return HttpResponse(
                "END Missing one or more required fields: sessionId, serviceCode, phoneNumber.",
                content_type="text/plain",
                status=400,
            )

        if text == "":
            response_text = (
                "CON Welcome to Smart Market\n"
                "1. Check market prices\n"
                "2. Weather outlook\n"
                "3. Exit"
            )
        elif text == "1":
            response_text = "END Market prices feature coming soon."
        elif text == "2":
            response_text = "END Weather outlook feature coming soon."
        elif text == "3":
            response_text = "END Thank you for using Smart Market."
        else:
            response_text = "END Invalid choice. Please try again."

        return HttpResponse(response_text, content_type="text/plain")
