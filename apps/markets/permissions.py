from rest_framework.permissions import BasePermission

from apps.auth.models import Profile


class HasMarketPermission(BasePermission):
    message = "You do not have permission to access markets."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True

        permission_code = getattr(view, "permission_codes", {}).get(request.method)
        if not permission_code:
            return False

        try:
            role = user.profile.role
        except Profile.DoesNotExist:
            return False

        return role.permission_links.filter(permission__code=permission_code).exists()
