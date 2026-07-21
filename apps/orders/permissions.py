from apps.auth.models import Profile
from apps.common.permissions import HasPermissionCode, user_has_permission_code


class IsOrderParticipant(HasPermissionCode):
    message = "You do not have permission to view or manage this order."

    def has_object_permission(self, request, view, obj):
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

        return obj.user == user or obj.listing.user == user
