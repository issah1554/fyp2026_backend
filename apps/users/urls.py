from django.urls import path

from .views import (
    PermissionDetailView,
    PermissionListCreateView,
    RoleDetailView,
    RoleListView,
    UserDetailView,
    UserListCreateView,
)

app_name = "users"

urlpatterns = [
    path("", UserListCreateView.as_view(), name="user-list"),
    path("roles/", RoleListView.as_view(), name="role-list"),
    path("roles/<str:role_id>/", RoleDetailView.as_view(), name="role-detail"),
    path("permissions/", PermissionListCreateView.as_view(), name="permission-list"),
    path("permissions/<str:permission_id>/", PermissionDetailView.as_view(), name="permission-detail"),
    path("<str:user_id>/", UserDetailView.as_view(), name="user-detail"),
]
