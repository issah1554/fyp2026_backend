from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Commodity, CommodityCategory, CommodityUnit, CommodityUnitMap


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
        fields = ["unit_id", "name", "symbol", "created_at"]
        read_only_fields = ["unit_id", "created_at"]


class CommoditySerializer(serializers.ModelSerializer):
    commodity_id = serializers.CharField(source="public_id", read_only=True)

    # ── read fields ──────────────────────────────────────────────────────────
    categories = serializers.SerializerMethodField()
    # 'unit' exposes the primary unit's symbol (backward-compatible plain string)
    unit = serializers.SerializerMethodField()
    # 'unit_detail' exposes the full primary unit object (backward-compatible)
    unit_detail = serializers.SerializerMethodField()
    # 'units' exposes all units as a list
    units = serializers.SerializerMethodField()

    # ── write fields ─────────────────────────────────────────────────────────
    # unit_id (singular) — backward-compatible: sets the one primary unit
    unit_id = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="public_id of the primary CommodityUnit for this commodity.",
    )
    # unit_ids (plural) — new: assign multiple units at once
    unit_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text=(
            "List of CommodityUnit public_ids to associate with this commodity. "
            "The first entry becomes the primary unit."
        ),
    )
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
            "unit_ids",
            "unit_detail",
            "units",
            "categories",
            "category_ids",
            "created_at",
        ]
        read_only_fields = [
            "commodity_id",
            "unit",
            "unit_detail",
            "units",
            "categories",
            "created_at",
        ]

    # ── read helpers ─────────────────────────────────────────────────────────

    def _get_primary_map(self, commodity):
        """Return the primary CommodityUnitMap entry, falling back to the first one."""
        maps = list(commodity.unit_maps.select_related("unit").all())
        primary = next((m for m in maps if m.is_primary), None)
        return primary or (maps[0] if maps else None)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_unit(self, commodity):
        """Backward-compatible single unit symbol string."""
        mapping = self._get_primary_map(commodity)
        return mapping.unit.symbol if mapping else ""

    @extend_schema_field(CommodityUnitSerializer(allow_null=True))
    def get_unit_detail(self, commodity):
        """Backward-compatible single unit detail object."""
        mapping = self._get_primary_map(commodity)
        return CommodityUnitSerializer(mapping.unit).data if mapping else None

    @extend_schema_field(CommodityUnitSerializer(many=True))
    def get_units(self, commodity):
        """Full list of all units associated with this commodity."""
        maps = commodity.unit_maps.select_related("unit").all()
        return CommodityUnitSerializer([m.unit for m in maps], many=True).data

    @extend_schema_field(CommodityCategorySerializer(many=True))
    def get_categories(self, commodity):
        return CommodityCategorySerializer(commodity.categories.all(), many=True).data

    # ── validation ───────────────────────────────────────────────────────────

    def validate_unit_id(self, value):
        if not value:
            return None
        unit = CommodityUnit.objects.filter(public_id=value).first()
        if not unit:
            raise serializers.ValidationError(
                f"CommodityUnit with public_id '{value}' does not exist."
            )
        return unit

    def validate_unit_ids(self, value):
        if not value:
            return []
        existing = {
            u.public_id: u
            for u in CommodityUnit.objects.filter(public_id__in=value)
        }
        missing = sorted(set(value) - set(existing.keys()))
        if missing:
            raise serializers.ValidationError(
                f"Unknown unit_id value(s): {', '.join(missing)}"
            )
        return list(existing.values())

    def validate_category_ids(self, value):
        existing_ids = set(
            CommodityCategory.objects.filter(public_id__in=value).values_list(
                "public_id", flat=True
            )
        )
        missing_ids = sorted(set(value) - existing_ids)
        if missing_ids:
            raise serializers.ValidationError(
                f"Unknown category_id value(s): {', '.join(missing_ids)}"
            )
        return value

    # ── write helpers ─────────────────────────────────────────────────────────

    def _apply_units(self, commodity, primary_unit, extra_units):
        """
        Set the commodity's units M2M.

        primary_unit  — a CommodityUnit instance (from unit_id) or None
        extra_units   — list of CommodityUnit instances (from unit_ids)
        """
        # Collect all units preserving order; primary_unit goes first
        all_units = []
        seen = set()
        if primary_unit:
            all_units.append((primary_unit, True))
            seen.add(primary_unit.pk)
        for unit in extra_units:
            if unit.pk not in seen:
                all_units.append((unit, False))
                seen.add(unit.pk)

        if not all_units:
            return

        # Clear existing mappings then recreate
        commodity.unit_maps.all().delete()
        CommodityUnitMap.objects.bulk_create([
            CommodityUnitMap(
                commodity=commodity,
                unit=unit,
                is_primary=is_primary,
            )
            for unit, is_primary in all_units
        ])

    # ── create / update ───────────────────────────────────────────────────────

    def create(self, validated_data):
        category_ids = validated_data.pop("category_ids", [])
        primary_unit = validated_data.pop("unit_id", None)
        extra_units = validated_data.pop("unit_ids", [])

        commodity = Commodity.objects.create(**validated_data)

        self._apply_units(commodity, primary_unit, extra_units)

        if category_ids:
            commodity.categories.set(
                CommodityCategory.objects.filter(public_id__in=category_ids)
            )
        return commodity

    def update(self, instance, validated_data):
        category_ids = validated_data.pop("category_ids", serializers.empty)
        primary_unit = validated_data.pop("unit_id", serializers.empty)
        extra_units = validated_data.pop("unit_ids", serializers.empty)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        # Only update units if at least one unit write-field was provided
        if primary_unit is not serializers.empty or extra_units is not serializers.empty:
            self._apply_units(
                instance,
                primary_unit if primary_unit is not serializers.empty else None,
                extra_units if extra_units is not serializers.empty else [],
            )

        if category_ids is not serializers.empty:
            instance.categories.set(
                CommodityCategory.objects.filter(public_id__in=category_ids)
            )
        return instance
