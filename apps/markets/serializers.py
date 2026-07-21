from rest_framework import serializers

from apps.areas.models import AdmArea
from apps.areas.serializers import AdmAreaSerializer
from apps.commodities.models import Commodity
from apps.commodities.serializers import CommoditySerializer

from .models import Market, MarketCommodityPrice


class MarketSerializer(serializers.ModelSerializer):
    market_id = serializers.CharField(source="public_id", read_only=True)
    admin_area = AdmAreaSerializer(read_only=True)
    admin_area_id = serializers.CharField(write_only=True)
    created_by_id = serializers.CharField(source="created_by.profile.public_id", read_only=True, default=None)
    updated_by_id = serializers.CharField(source="updated_by.profile.public_id", read_only=True, default=None)

    class Meta:
        model = Market
        fields = [
            "market_id",
            "name",
            "code",
            "admin_area",
            "admin_area_id",
            "address",
            "latitude",
            "longitude",
            "description",
            "status",
            "created_by_id",
            "updated_by_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["market_id", "admin_area", "created_by_id", "updated_by_id", "created_at", "updated_at"]

    def validate_admin_area_id(self, value):
        area = AdmArea.objects.filter(public_id=value).first()
        if not area:
            raise serializers.ValidationError(f"Administrative Area with public_id '{value}' does not exist.")
        return area

    def validate_code(self, value):
        if not value:
            return value
        queryset = Market.all_objects.filter(code=value, deleted_at__isnull=True)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A market with this code already exists.")
        return value

    def create(self, validated_data):
        admin_area = validated_data.pop("admin_area_id")
        request = self.context.get("request")
        return Market.objects.create(admin_area=admin_area, created_by=request.user, **validated_data)

    def update(self, instance, validated_data):
        admin_area = validated_data.pop("admin_area_id", None)
        if admin_area:
            instance.admin_area = admin_area
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            instance.updated_by = request.user
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class MarketCommodityPriceSerializer(serializers.ModelSerializer):
    price_id = serializers.CharField(source="public_id", read_only=True)
    market = MarketSerializer(read_only=True)
    market_id = serializers.CharField(write_only=True)
    commodity = CommoditySerializer(read_only=True)
    commodity_id = serializers.CharField(write_only=True)
    created_by_id = serializers.CharField(source="created_by.profile.public_id", read_only=True, default=None)
    updated_by_id = serializers.CharField(source="updated_by.profile.public_id", read_only=True, default=None)

    class Meta:
        model = MarketCommodityPrice
        fields = [
            "price_id",
            "market",
            "market_id",
            "commodity",
            "commodity_id",
            "price",
            "currency",
            "price_date",
            "created_by_id",
            "updated_by_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["price_id", "market", "commodity", "created_by_id", "updated_by_id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        self.fixed_market = kwargs.pop("fixed_market", None)
        super().__init__(*args, **kwargs)
        if self.fixed_market is not None:
            self.fields["market_id"].required = False

    def validate_market_id(self, value):
        market = Market.objects.filter(public_id=value).first()
        if not market:
            raise serializers.ValidationError(f"Market with public_id '{value}' does not exist.")
        return market

    def validate_commodity_id(self, value):
        commodity = Commodity.objects.filter(public_id=value).first()
        if not commodity:
            raise serializers.ValidationError(f"Commodity with public_id '{value}' does not exist.")
        return commodity

    def validate_currency(self, value):
        return value.upper()

    def validate(self, attrs):
        market = self.fixed_market or attrs.get("market_id") or getattr(self.instance, "market", None)
        commodity = attrs.get("commodity_id") or getattr(self.instance, "commodity", None)
        price_date = attrs.get("price_date") or getattr(self.instance, "price_date", None)
        if market and commodity and price_date:
            queryset = MarketCommodityPrice.all_objects.filter(
                market=market,
                commodity=commodity,
                price_date=price_date,
                deleted_at__isnull=True,
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    "A price for this market, commodity, and date already exists."
                )
        return attrs

    def create(self, validated_data):
        market = self.fixed_market or validated_data.pop("market_id")
        commodity = validated_data.pop("commodity_id")
        request = self.context.get("request")
        return MarketCommodityPrice.objects.create(
            market=market,
            commodity=commodity,
            created_by=request.user,
            **validated_data,
        )

    def update(self, instance, validated_data):
        market = validated_data.pop("market_id", None)
        commodity = validated_data.pop("commodity_id", None)
        if market:
            instance.market = market
        if commodity:
            instance.commodity = commodity
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            instance.updated_by = request.user
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
