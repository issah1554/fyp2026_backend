from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Commodity, CommodityCategory, CommodityUnit


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
