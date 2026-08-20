from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.common.validators import validate_international_phone_number
from .cloudinary_services import upload_profile_avatar
from .models import EmailVerificationToken, PasswordResetToken, Profile
from apps.users.models import Permission, Role

User = get_user_model()


def default_profile_role():
    return Role.objects.get(code=Profile.Role.FARMER)


class ProfileSerializer(serializers.ModelSerializer):
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
            "avatar_url",
            "is_email_verified",
            "email_verified_at",
        ]
        read_only_fields = ["email_verified_at"]

    @extend_schema_field(serializers.CharField)
    def get_role(self, profile):
        first_role = profile.roles.first()
        return first_role.code if first_role else ""


class UserSerializer(serializers.ModelSerializer):
    user_id = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["user_id", "username", "email", "first_name", "last_name", "profile"]
        read_only_fields = ["user_id"]

    @extend_schema_field(serializers.CharField)
    def get_user_id(self, user):
        profile, _created = Profile.objects.get_or_create(user=user)
        return profile.public_id

    @extend_schema_field(ProfileSerializer)
    def get_profile(self, user):
        profile, _created = Profile.objects.get_or_create(user=user)
        return ProfileSerializer(profile).data


class LoginUserSerializer(UserSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = [*UserSerializer.Meta.fields, "permissions"]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_permissions(self, user):
        profile, _created = Profile.objects.get_or_create(user=user)
        return list(
            Permission.objects.filter(role_links__role__profiles=profile)
            .order_by("code")
            .values_list("code", flat=True)
            .distinct()
        )


class SessionUserSerializer(LoginUserSerializer):
    pass


class SelfProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    organization = serializers.CharField(required=False, allow_blank=True, max_length=120)
    farm_location = serializers.CharField(required=False, allow_blank=True, max_length=150)
    farm_group = serializers.CharField(required=False, allow_blank=True, max_length=150)
    avatar_upload = serializers.ImageField(required=False, write_only=True)

    def validate_phone_number(self, value):
        return validate_international_phone_number(value) if value else value

    @transaction.atomic
    def update(self, instance, validated_data):
        profile, _created = Profile.objects.get_or_create(user=instance)
        avatar_upload = validated_data.pop("avatar_upload", None)

        for field in ["first_name", "last_name"]:
            if field in validated_data:
                setattr(instance, field, validated_data.pop(field))
        instance.save(update_fields=["first_name", "last_name"])

        for field, value in validated_data.items():
            setattr(profile, field, value)
        if avatar_upload is not None:
            profile.avatar_url = upload_profile_avatar(avatar_upload, instance)
        profile.save()
        return instance


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
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
            from apps.users.models import Role
            default_role = Role.objects.filter(code=Profile.Role.FARMER).first()
            if default_role:
                profile.roles.set([default_role])
                
        return user


class AuthTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(required=False, write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.username_field].required = False

    def validate(self, attrs):
        username = attrs.get(self.username_field)
        email = attrs.get("email")

        if not username and not email:
            raise serializers.ValidationError({
                self.username_field: ["This field or email is required."]
            })

        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user is not None:
                attrs[self.username_field] = getattr(user, self.username_field)
            else:
                attrs[self.username_field] = email
        elif username and "@" in username:
            user = User.objects.filter(email__iexact=username).first()
            if user is not None:
                attrs[self.username_field] = getattr(user, self.username_field)

        data = super().validate(attrs)
        profile, _created = Profile.objects.get_or_create(user=self.user)
        if not profile.is_email_verified:
            raise AuthenticationFailed("Email address is not verified.")
        data["user"] = LoginUserSerializer(self.user).data
        return data


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.RegexField(
        regex=r"^\d{6}$",
        error_messages={"invalid": "Enter a valid 6-digit verification code."},
    )

    def validate(self, attrs):
        verification_token = (
            EmailVerificationToken.objects.select_related("user", "user__profile")
            .filter(user__email__iexact=attrs["email"], token=attrs["code"])
            .first()
        )
        if verification_token is None or verification_token.is_used or verification_token.is_expired:
            raise serializers.ValidationError({"code": ["Verification code is invalid or expired."]})
        self.context["verification_token"] = verification_token
        return attrs

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


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        self.context["user"] = User.objects.filter(email__iexact=value).first()
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_token(self, value):
        reset_token = (
            PasswordResetToken.objects.select_related("user")
            .filter(token=value)
            .first()
        )
        if reset_token is None or reset_token.is_used or reset_token.is_expired:
            raise serializers.ValidationError("Token is invalid or expired.")
        self.context["reset_token"] = reset_token
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def save(self, **kwargs):
        reset_token = self.context["reset_token"]
        user = reset_token.user
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password"])
        reset_token.mark_used()
        return user


class AccountDeletionSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            raise serializers.ValidationError("Authenticated user not found.")
        if not user.check_password(value):
            raise serializers.ValidationError("Password is incorrect.")
        return value


class MobileLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].strip()
        password = attrs["password"]
        user = User.objects.filter(email__iexact=email).select_related("profile").first()

        if user is None or not user.check_password(password):
            raise AuthenticationFailed("Email address or password is incorrect.")
        profile, _created = Profile.objects.get_or_create(user=user)
        if profile.role != Profile.Role.MARKET_OFFICER:
            raise AuthenticationFailed("Mobile access is available for market officers only.")
        if not user.is_active:
            raise AuthenticationFailed("This account is inactive.")

        refresh = AuthTokenObtainPairSerializer.get_token(user)
        access = refresh.access_token

        return {
            "access": str(access),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        }
