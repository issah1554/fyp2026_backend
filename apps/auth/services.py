from datetime import timedelta
from secrets import token_urlsafe

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import EmailVerificationToken, PasswordResetToken


EMAIL_VERIFICATION_TOKEN_HOURS = 24
PASSWORD_RESET_TOKEN_HOURS = 1


def create_email_verification_token(user):
    return EmailVerificationToken.objects.create(
        user=user,
        token=token_urlsafe(48),
        expires_at=timezone.now() + timedelta(hours=EMAIL_VERIFICATION_TOKEN_HOURS),
    )


def send_email_verification(user):
    verification_token = create_email_verification_token(user)
    subject = "Verify your Smart Market email"
    message = (
        "Use this token to verify your Smart Market account:\n\n"
        f"{verification_token.token}\n\n"
        f"This token expires in {EMAIL_VERIFICATION_TOKEN_HOURS} hours."
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=False,
    )
    return verification_token


def create_password_reset_token(user):
    return PasswordResetToken.objects.create(
        user=user,
        token=token_urlsafe(48),
        expires_at=timezone.now() + timedelta(hours=PASSWORD_RESET_TOKEN_HOURS),
    )


def send_password_reset(user):
    reset_token = create_password_reset_token(user)
    reset_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')}/auth/reset-password?token={reset_token.token}"
    subject = "Reset your Smart Market password"
    message = (
        "Use this link to reset your Smart Market password:\n\n"
        f"{reset_url}\n\n"
        "Or copy this token into the password reset page:\n\n"
        f"{reset_token.token}\n\n"
        f"This token expires in {PASSWORD_RESET_TOKEN_HOURS} hour."
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=False,
    )
    return reset_token
