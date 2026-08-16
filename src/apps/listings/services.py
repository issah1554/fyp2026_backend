import cloudinary
import cloudinary.uploader
from django.conf import settings
from rest_framework import serializers
from urllib.parse import unquote, urlparse


def configure_cloudinary():
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


def listing_image_context(listing_image):
    listing = listing_image.listing
    context = {
        "image_id": listing_image.public_id,
        "listing_id": listing.public_id,
    }
    if listing.title:
        context["listing_title"] = listing.title
    if listing.commodity_id:
        context["commodity"] = listing.commodity.name
    return context


def cloudinary_public_id_from_url(image_url):
    parsed = urlparse(image_url)
    if "res.cloudinary.com" not in parsed.netloc:
        return ""

    marker = "/upload/"
    if marker not in parsed.path:
        return ""

    path_after_upload = parsed.path.split(marker, 1)[1]
    parts = path_after_upload.split("/")
    if parts and parts[0].startswith("v") and parts[0][1:].isdigit():
        parts = parts[1:]

    public_id = "/".join(parts)
    if "." in public_id.rsplit("/", 1)[-1]:
        public_id = public_id.rsplit(".", 1)[0]
    return unquote(public_id)


def sync_listing_image_cloudinary_metadata(listing_image):
    public_id = cloudinary_public_id_from_url(listing_image.image_url)
    if not public_id:
        return False

    configure_cloudinary()
    cloudinary.uploader.explicit(
        public_id,
        type="upload",
        resource_type="image",
        context=listing_image_context(listing_image),
    )
    return True


def upload_listing_image(image_file, listing_image=None):
    configure_cloudinary()
    upload_options = {
        "folder": settings.CLOUDINARY_LISTINGS_FOLDER,
        "resource_type": "image",
    }
    if listing_image:
        upload_options["context"] = listing_image_context(listing_image)

    result = cloudinary.uploader.upload(
        image_file,
        **upload_options,
    )
    image_url = result.get("secure_url") or result.get("url")
    if not image_url:
        raise serializers.ValidationError(
            {"images_upload": ["Cloudinary did not return an image URL."]}
        )
    return image_url
