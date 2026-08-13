from rest_framework import serializers

from apps.areas.models import AdmArea
from apps.areas.serializers import AdmAreaSerializer
from apps.commodities.serializers import CommoditySerializer
from apps.commodities.models import Commodity
from .models import CommodityListing, ListingImage
from .services import sync_listing_image_cloudinary_metadata, upload_listing_image


class UserSummarySerializer(serializers.Serializer):
    user_id = serializers.SerializerMethodField()
    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    full_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    def get_user_id(self, user):
        return getattr(getattr(user, "profile", None), "public_id", None)

    def get_full_name(self, user):
        full_name = user.get_full_name()
        return full_name or user.username

    def get_phone_number(self, user):
        return getattr(getattr(user, "profile", None), "phone_number", "")

    def get_organization(self, user):
        return getattr(getattr(user, "profile", None), "organization", "")

    def get_avatar_url(self, user):
        return getattr(getattr(user, "profile", None), "avatar_url", "")

    def get_role(self, user):
        role = getattr(getattr(user, "profile", None), "role", None)
        if not role:
            return None
        return {
            "code": role.code,
            "name": role.name,
        }


class ListingImageSerializer(serializers.ModelSerializer):
    image_id = serializers.CharField(source="public_id", read_only=True)

    class Meta:
        model = ListingImage
        fields = ["image_id", "image_url", "is_primary"]
        read_only_fields = ["image_id"]


class ListingImageUploadSerializer(serializers.Serializer):
    images_upload = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=True,
        allow_empty=False,
    )

    def create(self, validated_data):
        listing = self.context["listing"]
        created_images = []
        start_index = listing.images.count()

        for idx, image_file in enumerate(validated_data["images_upload"]):
            listing_image = ListingImage(
                listing=listing,
                is_primary=start_index == 0 and idx == 0,
            )
            listing_image.save()
            listing_image.image_url = upload_listing_image(image_file, listing_image=listing_image)
            listing_image.save(update_fields=["image_url"])
            created_images.append(listing_image)

        return created_images


class CommodityListingSerializer(serializers.ModelSerializer):
    listing_id = serializers.CharField(source="public_id", read_only=True)
    commodity = CommoditySerializer(read_only=True)
    commodity_id = serializers.CharField(write_only=True)
    adm_area = AdmAreaSerializer(read_only=True)
    adm_area_id = serializers.CharField(write_only=True)
    seller_id = serializers.CharField(source="user.profile.public_id", read_only=True, default=None)
    seller = UserSummarySerializer(source="user", read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    image_urls = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False
    )
    images_upload = serializers.ListField(
        child=serializers.ImageField(),
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
            "seller",
            "title",
            "description",
            "price",
            "quantity",
            "status",
            "images",
            "image_urls",
            "images_upload",
            "created_at",
        ]
        read_only_fields = ["listing_id", "commodity", "adm_area", "seller_id", "seller", "images", "created_at"]

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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        image_urls = attrs.get("image_urls")
        images_upload = attrs.get("images_upload")

        if self.instance is None:
            image_count = len(image_urls or []) + len(images_upload or [])
            if image_count < 3:
                raise serializers.ValidationError(
                    {"images_upload": "At least 3 listing images are required."}
                )

        return attrs

    def create(self, validated_data):
        commodity = validated_data.pop("commodity_id")
        adm_area = validated_data.pop("adm_area_id")
        image_urls = validated_data.pop("image_urls", [])
        images_upload = validated_data.pop("images_upload", [])
        
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        listing = CommodityListing.objects.create(
            commodity=commodity,
            adm_area=adm_area,
            user=user,
            **validated_data
        )
        
        for idx, url in enumerate(image_urls):
            listing_image = ListingImage.objects.create(
                listing=listing,
                image_url=url,
                is_primary=(idx == 0)
            )
            sync_listing_image_cloudinary_metadata(listing_image)

        upload_start_index = len(image_urls)
        for upload_idx, image_file in enumerate(images_upload):
            listing_image = ListingImage(
                listing=listing,
                is_primary=(upload_start_index + upload_idx == 0),
            )
            listing_image.save()
            listing_image.image_url = upload_listing_image(image_file, listing_image=listing_image)
            listing_image.save(update_fields=["image_url"])
        
        return listing

    def update(self, instance, validated_data):
        commodity = validated_data.pop("commodity_id", None)
        if commodity:
            instance.commodity = commodity
        adm_area = validated_data.pop("adm_area_id", None)
        if adm_area:
            instance.adm_area = adm_area
            
        image_urls = validated_data.pop("image_urls", None)
        images_upload = validated_data.pop("images_upload", None)
        if image_urls is not None or images_upload is not None:
            next_image_urls = image_urls or []
            instance.images.all().delete()
            for idx, url in enumerate(next_image_urls):
                listing_image = ListingImage.objects.create(
                    listing=instance,
                    image_url=url,
                    is_primary=(idx == 0)
                )
                sync_listing_image_cloudinary_metadata(listing_image)
            upload_start_index = len(next_image_urls)
            for upload_idx, image_file in enumerate(images_upload or []):
                listing_image = ListingImage(
                    listing=instance,
                    is_primary=(upload_start_index + upload_idx == 0),
                )
                listing_image.save()
                listing_image.image_url = upload_listing_image(image_file, listing_image=listing_image)
                listing_image.save(update_fields=["image_url"])

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        for listing_image in instance.images.all():
            sync_listing_image_cloudinary_metadata(listing_image)
        return instance
