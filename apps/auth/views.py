from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import AuthTokenObtainPairSerializer, RegisterSerializer, UserSerializer


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
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Auth"],
    request=AuthTokenObtainPairSerializer,
    responses={200: AuthTokenObtainPairSerializer},
)
class LoginView(TokenObtainPairView):
    serializer_class = AuthTokenObtainPairSerializer


@extend_schema(
    tags=["Auth"],
    request=TokenRefreshSerializer,
    responses={200: TokenRefreshSerializer},
)
class RefreshTokenView(TokenRefreshView):
    serializer_class = TokenRefreshSerializer


@extend_schema(
    tags=["Auth"],
    responses={200: UserSerializer},
)
class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


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
        return Response(
            {"detail": "Logout successful. Discard the access and refresh tokens on the client."},
            status=status.HTTP_200_OK,
        )
