from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.common.responses import mutation_payload, mutation_response, success_response
from apps.common.permissions import HasPermissionCode

from .serializers import (
    AccountDeletionSerializer,
    AuthTokenObtainPairSerializer,
    MobileLoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    ResendEmailVerificationSerializer,
    SessionUserSerializer,
    SelfProfileUpdateSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from .models import Profile
from .services import send_email_verification, send_password_reset


def get_frontend_origin(request):
    origin = request.headers.get("Origin")
    if origin:
        return origin

    referer = request.headers.get("Referer")
    if referer:
        return referer

    return None


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
        send_email_verification(user, frontend_origin=get_frontend_origin(request))
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
                send_email_verification(user, frontend_origin=get_frontend_origin(request))
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
)
class MeView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_classes = [HasPermissionCode]
    permission_codes = {
        "GET": "auth.me",
        "PATCH": "auth.me",
        "DELETE": "auth.account.delete",
    }

    @extend_schema(responses={200: SessionUserSerializer})
    def get(self, request):
        return success_response(SessionUserSerializer(request.user).data)

    @extend_schema(request=SelfProfileUpdateSerializer, responses={200: SessionUserSerializer})
    def patch(self, request):
        serializer = SelfProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return mutation_response(
            message="Profile updated successfully.",
            data=SessionUserSerializer(user).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(
        request=AccountDeletionSerializer,
        responses={200: OpenApiResponse(description="Authenticated account deleted.")},
    )
    def delete(self, request):
        serializer = AccountDeletionSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.delete()
        return mutation_response(
            message="Account deleted successfully.",
            status_code=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Auth"],
    request=None,
    responses={
        200: OpenApiResponse(description="Logout acknowledged. Discard tokens on the client."),
    },
)
class LogoutView(APIView):
    permission_classes = [HasPermissionCode]
    permission_codes = {
        "POST": "auth.logout",
    }

    def post(self, request):
        return mutation_response(
            message="Logout successful. Discard the access and refresh tokens on the client.",
            status_code=status.HTTP_200_OK,
        )


class MobileMarketOfficerMixin:
    permission_classes = [permissions.IsAuthenticated]

    def ensure_market_officer(self, user):
        profile, _created = Profile.objects.get_or_create(user=user)
        if not profile.has_role(Profile.Role.MARKET_OFFICER):
            raise PermissionDenied("Mobile access is available for market officers only.")
        return profile


@extend_schema(
    tags=["Mobile Auth"],
    request=MobileLoginSerializer,
    responses={200: MobileLoginSerializer},
)
class MobileLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MobileLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return mutation_response(
            message="Umeingia kwenye akaunti yako kwa mafanikio.",
            data=serializer.validated_data,
            status_code=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Mobile Auth"],
    responses={200: UserSerializer},
)
class MobileMeView(MobileMarketOfficerMixin, APIView):
    def get(self, request):
        self.ensure_market_officer(request.user)
        return success_response(UserSerializer(request.user).data)


@extend_schema(
    tags=["Mobile Auth"],
    responses={200: OpenApiResponse(description="Market officer dashboard payload.")},
)
class MobileDashboardView(MobileMarketOfficerMixin, APIView):
    def get(self, request):
        profile = self.ensure_market_officer(request.user)
        return success_response(
            {
                "user": UserSerializer(request.user).data,
                "profile_summary": {
                    "display_name": request.user.get_full_name() or request.user.email,
                    "role": profile.get_role_display(),
                    "email": request.user.email,
                    "organization": profile.organization,
                },
                "summary_cards": [
                    {
                        "label": "Active Markets",
                        "value": "18",
                        "change": "+3 this month",
                        "icon": "storefront",
                        "tone": "primary",
                    },
                    {
                        "label": "Price Records",
                        "value": "12,840",
                        "change": "+428 today",
                        "icon": "database",
                        "tone": "accent",
                    },
                    {
                        "label": "Pending Reviews",
                        "value": "34",
                        "change": "12 high priority",
                        "icon": "assignment_turned_in",
                        "tone": "warning",
                    },
                    {
                        "label": "Registered Users",
                        "value": "4,920",
                        "change": "+126 this week",
                        "icon": "groups",
                        "tone": "success",
                    },
                ],
                "collection_progress": [
                    {"market": "Ifakara Central", "commodity": "Rice", "progress": 96, "status": "Verified"},
                    {"market": "Mlimba Market", "commodity": "Maize", "progress": 88, "status": "Review"},
                    {"market": "Mang'ula Market", "commodity": "Tomatoes", "progress": 75, "status": "Pending"},
                    {"market": "Kidatu Market", "commodity": "Beans", "progress": 92, "status": "Verified"},
                ],
                "alerts": [
                    {
                        "title": "Rice price variance",
                        "detail": "Ifakara Central is 14% above the weekly district average.",
                        "icon": "trending_up",
                    },
                    {
                        "title": "Incomplete officer submissions",
                        "detail": "Three assigned markets have not completed afternoon updates.",
                        "icon": "warning_amber",
                    },
                    {
                        "title": "USSD usage spike",
                        "detail": "Commodity lookup sessions increased by 22% since yesterday.",
                        "icon": "phone_iphone",
                    },
                ],
                "forecast_rows": [
                    {"commodity": "Rice", "direction": "Rising", "confidence": "89%", "price": "TZS 2,850"},
                    {"commodity": "Maize", "direction": "Stable", "confidence": "82%", "price": "TZS 1,120"},
                    {"commodity": "Beans", "direction": "Rising", "confidence": "77%", "price": "TZS 3,400"},
                    {"commodity": "Tomatoes", "direction": "Falling", "confidence": "73%", "price": "TZS 1,650"},
                ],
                "pipeline_steps": ["Ingest", "Clean", "Predict"],
            }
        )
