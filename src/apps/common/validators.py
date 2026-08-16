import re

from rest_framework import serializers


PHONE_NUMBER_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
PHONE_NUMBER_ERROR = "Enter a phone number in international format, for example +255700000001."


def validate_international_phone_number(value):
    if value in (None, ""):
        return ""

    value = str(value).strip()
    if not PHONE_NUMBER_PATTERN.fullmatch(value):
        raise serializers.ValidationError(PHONE_NUMBER_ERROR)
    return value
