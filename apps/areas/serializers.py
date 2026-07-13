from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import AdmArea

AREA_PARENT_LEVELS = {
    AdmArea.Level.REGION: None,
    AdmArea.Level.DISTRICT: AdmArea.Level.REGION,
    AdmArea.Level.WARD: AdmArea.Level.DISTRICT,
}


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

    def validate(self, attrs):
        level = attrs.get("level", getattr(self.instance, "level", AdmArea.Level.REGION))
        parent = attrs.get("parent_id", getattr(self.instance, "parent", None))
        expected_parent_level = AREA_PARENT_LEVELS.get(level)

        if expected_parent_level is None:
            if parent is not None:
                raise serializers.ValidationError({"parent_id": "Regions must not include a parent."})
            return attrs

        if parent is None:
            raise serializers.ValidationError({"parent_id": f"{level.title()} areas must include a parent_id."})

        if parent.level != expected_parent_level:
            raise serializers.ValidationError(
                {"parent_id": f"{level.title()} areas must use a {expected_parent_level} parent."}
            )

        return attrs

    def create(self, validated_data):
        parent = validated_data.pop("parent_id", None)
        return AdmArea.objects.create(parent=parent, **validated_data)

    def update(self, instance, validated_data):
        if "parent_id" in validated_data:
            instance.parent = validated_data.pop("parent_id")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class AdmAreaPathImportSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=AdmArea.Level.choices)
    path = serializers.ListField(
        child=serializers.CharField(allow_blank=False, trim_whitespace=True),
        min_length=1,
        max_length=3,
    )

    expected_path_lengths = {
        AdmArea.Level.REGION: 1,
        AdmArea.Level.DISTRICT: 2,
        AdmArea.Level.WARD: 3,
    }

    path_levels = [
        AdmArea.Level.REGION,
        AdmArea.Level.DISTRICT,
        AdmArea.Level.WARD,
    ]

    def validate(self, attrs):
        level = attrs["level"]
        path = attrs["path"]
        expected_length = self.expected_path_lengths[level]

        if len(path) != expected_length:
            raise serializers.ValidationError(
                {"path": f"{level.title()} imports require a path with {expected_length} item(s)."}
            )

        normalized_path = [name.strip() for name in path]
        if any(not name for name in normalized_path):
            raise serializers.ValidationError({"path": "Path items cannot be blank."})

        attrs["path"] = normalized_path
        return attrs

    def create(self, validated_data):
        parent = None
        area = None

        for index, name in enumerate(validated_data["path"]):
            level = self.path_levels[index]
            area, _created = AdmArea.objects.get_or_create(
                name=name,
                level=level,
                parent=parent,
            )
            parent = area

        return area
