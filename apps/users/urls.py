from django.urls import path

from .views import (
    PermissionDetailView,
    PermissionListCreateView,
    RoleDetailView,
    RoleListCreateView,
    UserDetailView,
    UserListCreateView,
)

app_name = "users"

urlpatterns = [
    path("users", UserListCreateView.as_view(), name="user-list"),
    path("users/roles", RoleListCreateView.as_view(), name="role-list"),
    path("users/roles/<str:role_id>", RoleDetailView.as_view(), name="role-detail"),
    path("users/permissions", PermissionListCreateView.as_view(), name="permission-list"),
    path("users/permissions/<str:permission_id>", PermissionDetailView.as_view(), name="permission-detail"),
    path("users/<str:user_id>", UserDetailView.as_view(), name="user-detail"),
]
