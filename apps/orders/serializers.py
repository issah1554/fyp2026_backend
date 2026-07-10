from rest_framework import serializers

from apps.listings.models import CommodityListing
from apps.listings.serializers import CommodityListingSerializer
from .models import Order


class OrderSerializer(serializers.ModelSerializer):
    order_id = serializers.CharField(source="public_id", read_only=True)
    listing = CommodityListingSerializer(read_only=True)
    listing_id = serializers.CharField(write_only=True)
    buyer_id = serializers.CharField(source="user.profile.public_id", read_only=True, default=None)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_id",
            "listing",
            "listing_id",
            "buyer_id",
            "quantity",
            "total_price",
            "status",
            "created_at",
        ]
        read_only_fields = ["order_id", "listing", "buyer_id", "total_price", "created_at"]

    def validate_listing_id(self, value):
        listing = CommodityListing.objects.filter(public_id=value).first()
        if not listing:
            raise serializers.ValidationError(f"Commodity Listing with public_id '{value}' does not exist.")
        if listing.status != "active":
            raise serializers.ValidationError("This commodity listing is no longer active.")
        return listing

    def validate(self, attrs):
        listing = attrs.get("listing_id")
        quantity = attrs.get("quantity")

        if quantity <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be greater than 0."})

        if listing.quantity is not None and quantity > listing.quantity:
            raise serializers.ValidationError(
                {"quantity": f"Requested quantity {quantity} exceeds available quantity of {listing.quantity}."}
            )

        return attrs

    def create(self, validated_data):
        listing = validated_data.pop("listing_id")
        quantity = validated_data.get("quantity")
        
        # Calculate total price
        total_price = listing.price * quantity
        
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None
        
        # Deduct quantity from listing if listing quantity is set
        if listing.quantity is not None:
            listing.quantity -= quantity
            if listing.quantity == 0:
                listing.status = "sold"  # or similar status
            listing.save()

        order = Order.objects.create(
            listing=listing,
            user=user,
            total_price=total_price,
            **validated_data
        )
        return order
