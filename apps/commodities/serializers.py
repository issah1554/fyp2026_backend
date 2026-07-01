from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Commodity, CommodityCategory


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
