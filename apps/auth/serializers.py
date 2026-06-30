from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import EmailVerificationToken, Profile

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    is_email_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = Profile
        fields = ["role", "phone_number", "organization", "is_email_verified", "email_verified_at"]
        read_only_fields = ["email_verified_at"]


class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "profile"]
        read_only_fields = ["id"]

    @extend_schema_field(ProfileSerializer)
    def get_profile(self, user):
        profile, _created = Profile.objects.get_or_create(user=user)
        return ProfileSerializer(profile).data


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=Profile.Role.choices, default=Profile.Role.FARMER)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    organization = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "role",
            "phone_number",
            "organization",
        ]
        read_only_fields = ["id"]

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


class AuthTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        profile, _created = Profile.objects.get_or_create(user=self.user)
        if not profile.is_email_verified:
            raise AuthenticationFailed("Email address is not verified.")
        data["user"] = UserSerializer(self.user).data
        return data


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate_token(self, value):
        verification_token = (
            EmailVerificationToken.objects.select_related("user", "user__profile")
            .filter(token=value)
            .first()
        )
        if verification_token is None or verification_token.is_used or verification_token.is_expired:
            raise serializers.ValidationError("Token is invalid or expired.")
        self.context["verification_token"] = verification_token
        return value

    @transaction.atomic
    def save(self, **kwargs):
        verification_token = self.context["verification_token"]
        profile, _created = Profile.objects.get_or_create(user=verification_token.user)
        profile.mark_email_verified()
        verification_token.mark_used()
        return verification_token.user


class ResendEmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        self.context["user"] = User.objects.filter(email__iexact=value).first()
        return value
