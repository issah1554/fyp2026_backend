from django.test import TestCase, override_settings


class ApiErrorResponseMiddlewareTests(TestCase):
    @override_settings(DEBUG=True, ALLOWED_HOSTS=["testserver"])
    def test_api_404_uses_json_response_in_debug_mode(self):
        response = self.client.get("/api/v1/areas//")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["message"], "Endpoint not found.")
        self.assertEqual(response.json()["errors"]["path"], "/api/v1/areas//")
