from django.urls import path

from .views import MobileDashboardView, MobileLoginView, MobileMeView, RefreshTokenView

app_name = "mobile-auth"

urlpatterns = [
    path("login/", MobileLoginView.as_view(), name="login"),
    path("refresh/", RefreshTokenView.as_view(), name="refresh"),
    path("me/", MobileMeView.as_view(), name="me"),
    path("dashboard/", MobileDashboardView.as_view(), name="dashboard"),
]
