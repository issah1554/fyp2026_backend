from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Commodity, CommodityCategory, Market, MarketPriceRecord


class CommodityCategorySerializer(serializers.ModelSerializer):
    category_id = serializers.CharField(source="public_id", read_only=True)

    class Meta:
        model = CommodityCategory
        fields = ["category_id", "name", "description", "created_at"]
        read_only_fields = ["category_id", "created_at"]


class CommoditySerializer(serializers.ModelSerializer):
    commodity_id = serializers.CharField(source="public_id", read_only=True)
    categories = serializers.SerializerMethodField()
    category_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Commodity
        fields = [
            "commodity_id",
            "name",
            "unit",
            "description",
            "categories",
            "category_ids",
            "created_at",
        ]
        read_only_fields = ["commodity_id", "categories", "created_at"]

    @extend_schema_field(CommodityCategorySerializer(many=True))
    def get_categories(self, commodity):
        return CommodityCategorySerializer(commodity.categories.all(), many=True).data

    def validate_category_ids(self, value):
        existing_ids = set(
            CommodityCategory.objects.filter(public_id__in=value).values_list("public_id", flat=True)
        )
        missing_ids = sorted(set(value) - existing_ids)
        if missing_ids:
            raise serializers.ValidationError(f"Unknown category_id value(s): {', '.join(missing_ids)}")
        return value

    def create(self, validated_data):
        category_ids = validated_data.pop("category_ids", [])
        commodity = Commodity.objects.create(**validated_data)
        if category_ids:
            commodity.categories.set(CommodityCategory.objects.filter(public_id__in=category_ids))
        return commodity

    def update(self, instance, validated_data):
        category_ids = validated_data.pop("category_ids", serializers.empty)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if category_ids is not serializers.empty:
            instance.categories.set(CommodityCategory.objects.filter(public_id__in=category_ids))
        return instance


class MarketSerializer(serializers.ModelSerializer):
    market_id = serializers.CharField(source="public_id", read_only=True)

    class Meta:
        model = Market
        fields = ["market_id", "name", "is_active", "created_at"]
        read_only_fields = ["market_id", "created_at"]


class MarketPriceRecordSerializer(serializers.ModelSerializer):
    record_id = serializers.CharField(source="public_id", read_only=True)
    market_id = serializers.CharField(write_only=True)
    commodity_id = serializers.CharField(write_only=True)
    market = MarketSerializer(read_only=True)
    commodity = CommoditySerializer(read_only=True)
    officer = serializers.SerializerMethodField()

    class Meta:
        model = MarketPriceRecord
        fields = [
            "record_id",
            "market",
            "commodity",
            "market_id",
            "commodity_id",
            "price_type",
            "unit",
            "price",
            "currency",
            "record_date",
            "notes",
            "officer",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["record_id", "market", "commodity", "officer", "created_at", "updated_at"]

    @extend_schema_field(serializers.CharField)
    def get_officer(self, record):
        if record.created_by is None:
            return ""
        return record.created_by.get_full_name() or record.created_by.email or record.created_by.username

    def validate_market_id(self, value):
        market = Market.objects.filter(public_id=value, is_active=True).first()
        if market is None:
            raise serializers.ValidationError("Unknown or inactive market_id.")
        return value

    def validate_commodity_id(self, value):
        commodity = Commodity.objects.filter(public_id=value).first()
        if commodity is None:
            raise serializers.ValidationError("Unknown commodity_id.")
        return value

    def _resolve_relations(self, validated_data):
        market_id = validated_data.pop("market_id", None)
        commodity_id = validated_data.pop("commodity_id", None)
        if market_id is not None:
            validated_data["market"] = Market.objects.get(public_id=market_id)
        if commodity_id is not None:
            validated_data["commodity"] = Commodity.objects.get(public_id=commodity_id)
        return validated_data

    def create(self, validated_data):
        validated_data = self._resolve_relations(validated_data)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return MarketPriceRecord.objects.create(**validated_data)

    def update(self, instance, validated_data):
        validated_data = self._resolve_relations(validated_data)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
