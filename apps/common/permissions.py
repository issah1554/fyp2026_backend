from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.auth.models import Profile


def user_has_permission_code(user, permission_code):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    try:
        role = user.profile.role
    except Profile.DoesNotExist:
        return False
    return role.permission_links.filter(permission__code=permission_code).exists()


class HasPermissionCode(BasePermission):
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        permission_code = getattr(view, "permission_codes", {}).get(request.method)
        if not permission_code:
            return not hasattr(view, request.method.lower())
        return user_has_permission_code(request.user, permission_code)


class PublicReadPermissionCode(HasPermissionCode):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().has_permission(request, view)
