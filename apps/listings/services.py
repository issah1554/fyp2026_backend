import cloudinary
import cloudinary.uploader
from django.conf import settings
from rest_framework import serializers


def upload_listing_image(image_file):
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET:
        raise serializers.ValidationError(
            {"images_upload": ["Cloudinary is not configured on the server."]}
        )

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    result = cloudinary.uploader.upload(
        image_file,
        folder=settings.CLOUDINARY_LISTINGS_FOLDER,
        resource_type="image",
    )
    image_url = result.get("secure_url") or result.get("url")
    if not image_url:
        raise serializers.ValidationError(
            {"images_upload": ["Cloudinary did not return an image URL."]}
        )
    return image_url
