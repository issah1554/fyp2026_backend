from rest_framework import serializers

from apps.markets.models import RawCommodityPrice


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


class RawCommodityPriceSerializer(serializers.ModelSerializer):
    raw_price_id = serializers.CharField(source="public_id", read_only=True)
    market_name = serializers.CharField(source="market.name", read_only=True)
    commodity_name = serializers.CharField(source="commodity.name", read_only=True)
    unit_symbol = serializers.CharField(source="unit.symbol", read_only=True)
    normalized_price_id = serializers.CharField(source="normalized_price.public_id", read_only=True, default=None)
    source_id = serializers.CharField(source="source.public_id", read_only=True, default=None)
    source_label = serializers.CharField(source="source.name", read_only=True, default=None)

    class Meta:
        model = RawCommodityPrice
        fields = [
            "raw_price_id",
            "source_id",
            "source_key",
            "source_name",
            "source_label",
            "source_reference",
            "market_name",
            "commodity_name",
            "unit_symbol",
            "price_type",
            "price",
            "quantity",
            "min_price",
            "max_price",
            "currency",
            "price_date",
            "observed_at",
            "raw_payload",
            "normalized_price_id",
            "created_at",
        ]
