from rest_framework import serializers


class NormalizedMarketPriceSerializer(serializers.Serializer):
    source = serializers.CharField()
    commodity = serializers.CharField()
    price_tzs = serializers.FloatField(allow_null=True)
    price_usd = serializers.FloatField(allow_null=True)
    market = serializers.CharField(allow_null=True, required=False)
    volume = serializers.FloatField(allow_null=True, required=False)
    confidence = serializers.FloatField(allow_null=True, required=False)
    delay_minutes = serializers.IntegerField(allow_null=True, required=False)
    timestamp = serializers.CharField(allow_null=True)
    raw = serializers.DictField(required=False)
