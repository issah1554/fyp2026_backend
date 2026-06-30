from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    MeView,
    RefreshTokenView,
    RegisterView,
    ResendEmailVerificationView,
    VerifyEmailView,
)

app_name = "auth"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path("email/verify/", VerifyEmailView.as_view(), name="email-verify"),
    path("email/resend/", ResendEmailVerificationView.as_view(), name="email-resend"),
    path("me/", MeView.as_view(), name="me"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
