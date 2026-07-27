from rest_framework.permissions import SAFE_METHODS

from apps.auth.models import Profile
from apps.common.permissions import PublicReadPermissionCode, user_has_permission_code


class IsSellerOrReadOnly(PublicReadPermissionCode):
    message = "You do not have permission to perform this action on this listing."

    def has_permission(self, request, view):
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        permission_code = getattr(view, "permission_codes", {}).get(request.method)
        if not user_has_permission_code(user, permission_code):
            return False
        if user.is_staff or user.is_superuser:
            return True
        try:
            if user.profile.role.code == Profile.Role.ADMIN:
                return True
        except Profile.DoesNotExist:
            pass
        return obj.user == user
