from django.urls import path

from .views import UssdMenuView

app_name = "ussd"

urlpatterns = [
    path("menu", UssdMenuView.as_view(), name="menu-no-slash"),
    path("menu/", UssdMenuView.as_view(), name="menu"),
]
