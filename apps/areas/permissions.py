from apps.common.permissions import HasPermissionCode


class IsAdminOrReadOnly(HasPermissionCode):
    message = "You do not have permission to manage administrative areas."
