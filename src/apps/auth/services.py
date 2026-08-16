from datetime import timedelta
from secrets import randbelow, token_urlsafe

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import EmailVerificationToken, PasswordResetToken


EMAIL_VERIFICATION_TOKEN_HOURS = 24
PASSWORD_RESET_TOKEN_HOURS = 1
EMAIL_VERIFICATION_CODE_LENGTH = 6


def generate_email_verification_code():
    return f"{randbelow(10 ** EMAIL_VERIFICATION_CODE_LENGTH):0{EMAIL_VERIFICATION_CODE_LENGTH}d}"


def create_email_verification_token(user):
    expires_at = timezone.now() + timedelta(hours=EMAIL_VERIFICATION_TOKEN_HOURS)
    for _attempt in range(100):
        token = generate_email_verification_code()
        if not EmailVerificationToken.objects.filter(token=token).exists():
            return EmailVerificationToken.objects.create(
                user=user,
                token=token,
                expires_at=expires_at,
            )
    raise RuntimeError("Unable to generate a unique email verification code.")


def send_email_verification(user, frontend_origin=None):
    verification_token = create_email_verification_token(user)
    subject = "Verify your Smart Market email"
    context = {
        "user": user,
        "verification_code": verification_token.token,
        "expires_in_hours": EMAIL_VERIFICATION_TOKEN_HOURS,
    }
    message = (
        "Verify your Smart Market account using this code:\n\n"
        f"{verification_token.token}\n\n"
        f"This code expires in {EMAIL_VERIFICATION_TOKEN_HOURS} hours."
    )
    html_message = render_to_string("auth/email_verification.html", context)
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=False,
        html_message=html_message,
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
