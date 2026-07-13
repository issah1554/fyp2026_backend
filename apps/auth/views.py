from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.common.responses import mutation_payload, mutation_response, success_response

from .serializers import (
    AuthTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    ResendEmailVerificationSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from .models import Profile
from .services import send_email_verification, send_password_reset


@extend_schema(
    tags=["Auth"],
    request=RegisterSerializer,
    responses={201: UserSerializer},
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_email_verification(user)
        return mutation_response(
            message="User registered successfully. Check your email to verify your account.",
            data=UserSerializer(user).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Auth"],
    request=AuthTokenObtainPairSerializer,
    responses={200: AuthTokenObtainPairSerializer},
)
class LoginView(TokenObtainPairView):
    serializer_class = AuthTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.data = mutation_payload(message="Login successful.", data=response.data)
        return response


@extend_schema(
    tags=["Auth"],
    request=TokenRefreshSerializer,
    responses={200: TokenRefreshSerializer},
)
class RefreshTokenView(TokenRefreshView):
    serializer_class = TokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.data = mutation_payload(message="Token refreshed successfully.", data=response.data)
        return response


@extend_schema(
    tags=["Auth"],
    request=VerifyEmailSerializer,
    responses={200: UserSerializer},
)
class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return mutation_response(
            message="Email verified successfully.",
            data=UserSerializer(user).data,
            status_code=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Auth"],
    request=ResendEmailVerificationSerializer,
    responses={200: OpenApiResponse(description="Email verification resend request accepted.")},
)
class ResendEmailVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResendEmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.context.get("user")
        if user is not None:
            profile, _created = Profile.objects.get_or_create(user=user)
            if not profile.is_email_verified:
                send_email_verification(user)
        return mutation_response(
            message="If the account exists and is unverified, a verification email has been sent.",
            status_code=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Auth"],
    request=PasswordResetRequestSerializer,
    responses={200: OpenApiResponse(description="Password reset request accepted.")},
)
class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.context.get("user")
        if user is not None:
            send_password_reset(user)
        return mutation_response(
            message="If the account exists, a password reset link has been sent.",
            status_code=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Auth"],
    request=PasswordResetConfirmSerializer,
    responses={200: OpenApiResponse(description="Password reset completed.")},
)
class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return mutation_response(
            message="Password reset successful.",
            status_code=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Auth"],
    responses={200: UserSerializer},
)
class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return success_response(UserSerializer(request.user).data)


@extend_schema(
    tags=["Auth"],
    request=None,
    responses={
        200: OpenApiResponse(description="Logout acknowledged. Discard tokens on the client."),
    },
)
class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        return mutation_response(
            message="Logout successful. Discard the access and refresh tokens on the client.",
            status_code=status.HTTP_200_OK,
        )
