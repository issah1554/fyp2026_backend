from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.commodities.serializers import CommoditySerializer
from apps.commodities.models import Commodity
from .models import AdmArea, CommodityListing, ListingImage


class AdmAreaSerializer(serializers.ModelSerializer):
    area_id = serializers.CharField(source="public_id", read_only=True)
    parent_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    parent = serializers.SerializerMethodField()

    class Meta:
        model = AdmArea
        fields = ["area_id", "name", "parent_id", "parent", "level", "created_at"]
        read_only_fields = ["area_id", "parent", "created_at"]

    @extend_schema_field(serializers.DictField)
    def get_parent(self, obj):
        if obj.parent:
            return {
                "area_id": obj.parent.public_id,
                "name": obj.parent.name,
                "level": obj.parent.level,
            }
        return None

    def validate_parent_id(self, value):
        if value:
            parent = AdmArea.objects.filter(public_id=value).first()
            if not parent:
                raise serializers.ValidationError(f"Administrative Area with public_id '{value}' does not exist.")
            return parent
        return None

    def create(self, validated_data):
        parent = validated_data.pop("parent_id", None)
        area = AdmArea.objects.create(parent=parent, **validated_data)
        return area

    def update(self, instance, validated_data):
        if "parent_id" in validated_data:
            instance.parent = validated_data.pop("parent_id")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class ListingImageSerializer(serializers.ModelSerializer):
    image_id = serializers.CharField(source="public_id", read_only=True)

    class Meta:
        model = ListingImage
        fields = ["image_id", "image_url", "is_primary"]
        read_only_fields = ["image_id"]


class CommodityListingSerializer(serializers.ModelSerializer):
    listing_id = serializers.CharField(source="public_id", read_only=True)
    commodity = CommoditySerializer(read_only=True)
    commodity_id = serializers.CharField(write_only=True)
    adm_area = AdmAreaSerializer(read_only=True)
    adm_area_id = serializers.CharField(write_only=True)
    seller_id = serializers.CharField(source="user.profile.public_id", read_only=True, default=None)
    images = ListingImageSerializer(many=True, read_only=True)
    image_urls = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = CommodityListing
        fields = [
            "listing_id",
            "commodity",
            "commodity_id",
            "adm_area",
            "adm_area_id",
            "seller_id",
            "title",
            "description",
            "price",
            "quantity",
            "status",
            "images",
            "image_urls",
            "created_at",
        ]
        read_only_fields = ["listing_id", "commodity", "adm_area", "seller_id", "images", "created_at"]

    def validate_commodity_id(self, value):
        commodity = Commodity.objects.filter(public_id=value).first()
        if not commodity:
            raise serializers.ValidationError(f"Commodity with public_id '{value}' does not exist.")
        return commodity

    def validate_adm_area_id(self, value):
        area = AdmArea.objects.filter(public_id=value).first()
        if not area:
            raise serializers.ValidationError(f"Administrative Area with public_id '{value}' does not exist.")
        return area

    def create(self, validated_data):
        commodity = validated_data.pop("commodity_id")
        adm_area = validated_data.pop("adm_area_id")
        image_urls = validated_data.pop("image_urls", [])
        
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        listing = CommodityListing.objects.create(
            commodity=commodity,
            adm_area=adm_area,
            user=user,
            **validated_data
        )
        
        for idx, url in enumerate(image_urls):
            ListingImage.objects.create(
                listing=listing,
                image_url=url,
                is_primary=(idx == 0)
            )
        
        return listing

    def update(self, instance, validated_data):
        commodity = validated_data.pop("commodity_id", None)
        if commodity:
            instance.commodity = commodity
        adm_area = validated_data.pop("adm_area_id", None)
        if adm_area:
            instance.adm_area = adm_area
            
        image_urls = validated_data.pop("image_urls", None)
        if image_urls is not None:
            instance.images.all().delete()
            for idx, url in enumerate(image_urls):
                ListingImage.objects.create(
                    listing=instance,
                    image_url=url,
                    is_primary=(idx == 0)
                )

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
