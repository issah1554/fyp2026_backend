from django.urls import path

from .views import UserDetailView, UserListCreateView

app_name = "users"

urlpatterns = [
    path("", UserListCreateView.as_view(), name="user-list"),
    path("<str:user_id>/", UserDetailView.as_view(), name="user-detail"),
]
