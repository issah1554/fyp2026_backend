from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.auth.models import Profile
from apps.common.validators import validate_international_phone_number

from .models import Permission, Role, RolePermission

User = get_user_model()


def default_profile_role():
    return Role.objects.get(code=Profile.Role.FARMER)


class ManagedProfileSerializer(serializers.ModelSerializer):
    is_email_verified = serializers.BooleanField(read_only=True)
    roles = serializers.SlugRelatedField(slug_field="code", queryset=Role.objects.all(), many=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "role",
            "roles",
            "phone_number",
            "organization",
            "farm_location",
            "farm_group",
            "is_email_verified",
            "email_verified_at",
        ]
        read_only_fields = ["is_email_verified", "email_verified_at"]

    @extend_schema_field(serializers.CharField)
    def get_role(self, profile):
        first_role = profile.roles.first()
        return first_role.code if first_role else ""


class ManagedUserSerializer(serializers.ModelSerializer):
    user_id = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "user_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
            "profile",
        ]
        read_only_fields = ["user_id", "date_joined", "last_login"]

    @extend_schema_field(serializers.CharField)
    def get_user_id(self, user):
        profile, _created = Profile.objects.get_or_create(user=user)
        return profile.public_id

    @extend_schema_field(ManagedProfileSerializer)
    def get_profile(self, user):
        profile, _created = Profile.objects.get_or_create(user=user)
        return ManagedProfileSerializer(profile).data


class ManagedUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.SlugRelatedField(slug_field="code", queryset=Role.objects.all(), required=False)
    roles = serializers.SlugRelatedField(slug_field="code", queryset=Role.objects.all(), many=True, required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    organization = serializers.CharField(required=False, allow_blank=True)
    farm_location = serializers.CharField(required=False, allow_blank=True)
    farm_group = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "role",
            "roles",
            "phone_number",
            "organization",
            "farm_location",
            "farm_group",
        ]

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_phone_number(self, value):
        return validate_international_phone_number(value)

    @transaction.atomic
    def create(self, validated_data):
        roles_val = validated_data.pop("roles", None)
        role_val = validated_data.pop("role", None)
        profile_data = {
            "phone_number": validated_data.pop("phone_number", ""),
            "organization": validated_data.pop("organization", ""),
            "farm_location": validated_data.pop("farm_location", ""),
            "farm_group": validated_data.pop("farm_group", ""),
        }
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        profile = Profile.objects.create(user=user, **profile_data)
        
        if roles_val is not None:
            profile.roles.set(roles_val)
        elif role_val is not None:
            profile.roles.set([role_val])
        else:
            default_role = Role.objects.filter(code=Profile.Role.FARMER).first()
            if default_role:
                profile.roles.set([default_role])
        return user


class ManagedUserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.SlugRelatedField(slug_field="code", queryset=Role.objects.all(), required=False)
    roles = serializers.SlugRelatedField(slug_field="code", queryset=Role.objects.all(), many=True, required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    organization = serializers.CharField(required=False, allow_blank=True)
    farm_location = serializers.CharField(required=False, allow_blank=True)
    farm_group = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "role",
            "roles",
            "phone_number",
            "organization",
            "farm_location",
            "farm_group",
        ]

    def validate_email(self, value):
        queryset = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if value and queryset.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_phone_number(self, value):
        return validate_international_phone_number(value)

    def validate(self, attrs):
        request = self.context.get("request")
        current_profile, _created = Profile.objects.get_or_create(user=self.instance)
        
        current_has_admin = current_profile.roles.filter(code=Profile.Role.ADMIN).exists()
        next_has_admin = current_has_admin
        
        if "roles" in attrs:
            next_has_admin = any(r.code == Profile.Role.ADMIN for r in attrs["roles"])
        elif "role" in attrs:
            next_has_admin = attrs["role"].code == Profile.Role.ADMIN
            
        next_is_active = attrs.get("is_active", self.instance.is_active)
        
        removes_admin_role = current_has_admin and not next_has_admin
        deactivates_admin = current_has_admin and next_is_active is False

        if (removes_admin_role or deactivates_admin) and Profile.objects.filter(roles__code=Profile.Role.ADMIN, user__is_active=True).count() <= 1:
            raise serializers.ValidationError("At least one active admin must remain in the system.")

        if request is not None and self.instance != request.user:
            restricted_fields = ["email", "first_name", "last_name", "phone_number", "username"]
            for field in restricted_fields:
                if field in attrs:
                    current_value = getattr(self.instance, field, None)
                    if current_value is None and field == "phone_number":
                        profile = getattr(self.instance, "profile", None)
                        current_value = getattr(profile, "phone_number", None) if profile else None
                    new_value = attrs[field]
                    if new_value != current_value:
                        raise serializers.ValidationError(
                            {field: f"Administrators are restricted from editing another user's {field.replace('_', ' ')}."}
                        )
            return attrs

        removes_own_admin_role = current_has_admin and not next_has_admin
        removes_staff_access = attrs.get("is_staff") is False and request.user.is_staff
        removes_superuser_access = attrs.get("is_superuser") is False and request.user.is_superuser

        if attrs.get("is_active") is False or removes_own_admin_role or removes_staff_access or removes_superuser_access:
            raise serializers.ValidationError("You cannot remove your own admin access.")

        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        roles_val = validated_data.pop("roles", serializers.empty)
        role_val = validated_data.pop("role", serializers.empty)
        profile_fields = {
            "phone_number": validated_data.pop("phone_number", serializers.empty),
            "organization": validated_data.pop("organization", serializers.empty),
            "farm_location": validated_data.pop("farm_location", serializers.empty),
            "farm_group": validated_data.pop("farm_group", serializers.empty),
        }

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        profile, _created = Profile.objects.get_or_create(user=instance)
        
        if roles_val is not serializers.empty:
            profile.roles.set(roles_val)
        elif role_val is not serializers.empty:
            profile.roles.set([role_val])
            
        profile_update_fields = []
        for field, value in profile_fields.items():
            if value is not serializers.empty:
                setattr(profile, field, value)
                profile_update_fields.append(field)
        if profile_update_fields:
            profile_update_fields.append("updated_at")
            profile.save(update_fields=profile_update_fields)

        return instance


class PermissionSerializer(serializers.ModelSerializer):
    permission_id = serializers.CharField(source="public_id", read_only=True)

    class Meta:
        model = Permission
        fields = ["permission_id", "code", "name", "description", "created_at"]
        read_only_fields = ["permission_id", "created_at"]


class RoleSerializer(serializers.Serializer):
    role_id = serializers.CharField(source="public_id", read_only=True)
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    is_system = serializers.BooleanField(read_only=True)
    permission_ids = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    def get_permission_ids(self, role):
        return list(
            RolePermission.objects.filter(role=role).values_list("permission__public_id", flat=True)
        )

    def get_permissions(self, role):
        permissions = Permission.objects.filter(role_links__role=role).distinct()
        return PermissionSerializer(permissions, many=True).data


class RoleCreateUpdateSerializer(serializers.ModelSerializer):
    permission_ids = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)

    class Meta:
        model = Role
        fields = ["code", "name", "description", "permission_ids"]

    def validate_code(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError("Role code is required.")
        if not value.replace("_", "").isalnum():
            raise serializers.ValidationError("Role code may only contain letters, numbers, and underscores.")
        queryset = Role.objects.filter(code=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A role with this code already exists.")
        return value

    def validate_permission_ids(self, value):
        existing_ids = set(Permission.objects.filter(public_id__in=value).values_list("public_id", flat=True))
        missing_ids = sorted(set(value) - existing_ids)
        if missing_ids:
            raise serializers.ValidationError(f"Unknown permission_id value(s): {', '.join(missing_ids)}")
        return value

    def create(self, validated_data):
        permission_ids = validated_data.pop("permission_ids", [])
        role = Role.objects.create(is_system=False, **validated_data)
        if permission_ids:
            permissions = Permission.objects.filter(public_id__in=permission_ids)
            RolePermission.objects.bulk_create(
                [RolePermission(role=role, permission=permission) for permission in permissions],
                ignore_conflicts=True,
            )
        return role

    def update(self, instance, validated_data):
        permission_ids = validated_data.pop("permission_ids", serializers.empty)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if permission_ids is not serializers.empty:
            permissions = Permission.objects.filter(public_id__in=permission_ids)
            RolePermission.objects.filter(role=instance).delete()
            RolePermission.objects.bulk_create(
                [RolePermission(role=instance, permission=permission) for permission in permissions],
                ignore_conflicts=True,
            )
        return instance


class RolePermissionUpdateSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True)

    def validate_permission_ids(self, value):
        existing_ids = set(Permission.objects.filter(public_id__in=value).values_list("public_id", flat=True))
        missing_ids = sorted(set(value) - existing_ids)
        if missing_ids:
            raise serializers.ValidationError(f"Unknown permission_id value(s): {', '.join(missing_ids)}")
        return value
