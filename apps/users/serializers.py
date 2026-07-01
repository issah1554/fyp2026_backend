from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.auth.models import Profile

User = get_user_model()


class ManagedProfileSerializer(serializers.ModelSerializer):
    is_email_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "role",
            "phone_number",
            "organization",
            "is_email_verified",
            "email_verified_at",
        ]
        read_only_fields = ["is_email_verified", "email_verified_at"]


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
    role = serializers.ChoiceField(choices=Profile.Role.choices, default=Profile.Role.FARMER)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    organization = serializers.CharField(required=False, allow_blank=True)

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
            "phone_number",
            "organization",
        ]

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        profile_data = {
            "role": validated_data.pop("role", Profile.Role.FARMER),
            "phone_number": validated_data.pop("phone_number", ""),
            "organization": validated_data.pop("organization", ""),
        }
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        Profile.objects.create(user=user, **profile_data)
        return user


class ManagedUserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=Profile.Role.choices, required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    organization = serializers.CharField(required=False, allow_blank=True)

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
            "phone_number",
            "organization",
        ]

    def validate_email(self, value):
        queryset = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if value and queryset.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if request is None or self.instance != request.user:
            return attrs

        profile_role = attrs.get("role")
        removes_admin_role = profile_role is not None and profile_role != Profile.Role.ADMIN
        removes_staff_access = attrs.get("is_staff") is False and request.user.is_staff
        removes_superuser_access = attrs.get("is_superuser") is False and request.user.is_superuser

        if attrs.get("is_active") is False or removes_admin_role or removes_staff_access or removes_superuser_access:
            raise serializers.ValidationError("You cannot remove your own admin access.")

        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        profile_fields = {
            "role": validated_data.pop("role", serializers.empty),
            "phone_number": validated_data.pop("phone_number", serializers.empty),
            "organization": validated_data.pop("organization", serializers.empty),
        }

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        profile, _created = Profile.objects.get_or_create(user=instance)
        profile_update_fields = []
        for field, value in profile_fields.items():
            if value is not serializers.empty:
                setattr(profile, field, value)
                profile_update_fields.append(field)
        if profile_update_fields:
            profile_update_fields.append("updated_at")
            profile.save(update_fields=profile_update_fields)

        return instance
