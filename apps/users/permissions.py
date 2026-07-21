from apps.common.permissions import HasPermissionCode


class IsUserAdmin(HasPermissionCode):
    message = "You do not have permission to manage users."
