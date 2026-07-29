from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Commodity, CommodityCategory, CommodityUnit
from .models import Commodity, CommodityCategory, Market, MarketPriceRecord


class CommodityCategorySerializer(serializers.ModelSerializer):
    category_id = serializers.CharField(source="public_id", read_only=True)

    class Meta:
        model = CommodityCategory
        fields = ["category_id", "name", "description", "created_at"]
        read_only_fields = ["category_id", "created_at"]


class CommodityUnitSerializer(serializers.ModelSerializer):
    unit_id = serializers.CharField(source="public_id", read_only=True)

    class Meta:
        model = CommodityUnit
        fields = ["unit_id", "name", "symbol", "description", "created_at"]
        read_only_fields = ["unit_id", "created_at"]


class CommoditySerializer(serializers.ModelSerializer):
    commodity_id = serializers.CharField(source="public_id", read_only=True)
    categories = serializers.SerializerMethodField()
    unit_detail = serializers.SerializerMethodField()
    unit_id = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
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
            "unit_id",
            "unit_detail",
            "description",
            "categories",
            "category_ids",
            "created_at",
        ]
        read_only_fields = ["commodity_id", "unit_detail", "categories", "created_at"]

    @extend_schema_field(CommodityCategorySerializer(many=True))
    def get_categories(self, commodity):
        return CommodityCategorySerializer(commodity.categories.all(), many=True).data

    @extend_schema_field(CommodityUnitSerializer)
    def get_unit_detail(self, commodity):
        if commodity.unit_ref:
            return CommodityUnitSerializer(commodity.unit_ref).data
        return None

    def validate_unit_id(self, value):
        if not value:
            return None

        unit = CommodityUnit.objects.filter(public_id=value).first()
        if not unit:
            raise serializers.ValidationError(f"Commodity Unit with public_id '{value}' does not exist.")
        return unit

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
        unit = validated_data.pop("unit_id", None)
        if unit:
            validated_data["unit_ref"] = unit
            validated_data["unit"] = unit.symbol
        commodity = Commodity.objects.create(**validated_data)
        if category_ids:
            commodity.categories.set(CommodityCategory.objects.filter(public_id__in=category_ids))
        return commodity

    def update(self, instance, validated_data):
        category_ids = validated_data.pop("category_ids", serializers.empty)
        unit = validated_data.pop("unit_id", serializers.empty)
        if unit is not serializers.empty:
            instance.unit_ref = unit
            if unit:
                instance.unit = unit.symbol
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
