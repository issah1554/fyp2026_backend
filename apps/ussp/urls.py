from django.urls import path

from .views import UssdMenuView

app_name = "ussp"

urlpatterns = [
    path("menu/", UssdMenuView.as_view(), name="menu"),
]
