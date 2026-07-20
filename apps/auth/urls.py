from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshTokenView,
    RegisterView,
    ResendEmailVerificationView,
    VerifyEmailView,
)

app_name = "auth"

urlpatterns = [
    path("auth/register", RegisterView.as_view(), name="register"),
    path("auth/login", LoginView.as_view(), name="login"),
    path("auth/token/refresh", RefreshTokenView.as_view(), name="token-refresh"),
    path("auth/email/verify", VerifyEmailView.as_view(), name="email-verify"),
    path("auth/email/resend", ResendEmailVerificationView.as_view(), name="email-resend"),
    path("auth/password/reset/request", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("auth/password/reset/confirm", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("auth/me", MeView.as_view(), name="me"),
    path("auth/logout", LogoutView.as_view(), name="logout"),
]
