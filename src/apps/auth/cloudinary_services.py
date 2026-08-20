import cloudinary
import cloudinary.uploader
from django.conf import settings
from rest_framework import serializers


def configure_cloudinary():
    if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET:
        raise serializers.ValidationError(
            {"avatar_upload": ["Cloudinary is not configured on the server."]}
        )

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


def upload_profile_avatar(image_file, user):
    configure_cloudinary()
    profile = user.profile
    result = cloudinary.uploader.upload(
        image_file,
        folder=settings.CLOUDINARY_PROFILES_FOLDER,
        resource_type="image",
        public_id=profile.public_id,
        overwrite=True,
        invalidate=True,
        context={
            "user_id": profile.public_id,
            "email": user.email,
            "username": user.username,
        },
    )
    image_url = result.get("secure_url") or result.get("url")
    if not image_url:
        raise serializers.ValidationError(
            {"avatar_upload": ["Cloudinary did not return an avatar URL."]}
        )
    return image_url
