import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


logger = logging.getLogger(__name__)


def send_ussd_result_sms(phone_number, message):
    if not phone_number or not message:
        return False

    api_key = getattr(settings, "AFRICASTALKING_API_KEY", "").strip()
    username = getattr(settings, "AFRICASTALKING_USERNAME", "").strip()
    sender_id = getattr(settings, "AFRICASTALKING_SENDER_ID", "").strip()
    base_url = getattr(
        settings,
        "AFRICASTALKING_SMS_URL",
        "https://api.africastalking.com/version1/messaging",
    ).strip()

    if not api_key or not username:
        logger.info("Skipping USSD result SMS because Africa's Talking credentials are not configured.")
        return False

    payload = {
        "username": username,
        "to": phone_number,
        "message": message,
    }
    if sender_id:
        payload["from"] = sender_id

    encoded_payload = urlencode(payload).encode("utf-8")
    request = Request(
        base_url,
        data=encoded_payload,
        headers={
            "apiKey": api_key,
            "Accept": "application/x-www-form-urlencoded",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    timeout = getattr(settings, "AFRICASTALKING_SMS_TIMEOUT_SECONDS", 10)
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= status_code < 300:
                return True
            logger.warning("Africa's Talking SMS request returned status %s.", status_code)
            return False
    except HTTPError as exc:
        logger.warning("Africa's Talking SMS request failed with HTTP %s.", exc.code)
    except URLError as exc:
        logger.warning("Africa's Talking SMS request failed: %s", exc.reason)
    except Exception:
        logger.exception("Unexpected error while sending USSD result SMS.")
    return False
