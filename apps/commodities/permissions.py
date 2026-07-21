from apps.common.permissions import HasPermissionCode


class IsAdminOrAuthenticatedReadOnly(HasPermissionCode):
    message = "You do not have permission to manage commodities."
