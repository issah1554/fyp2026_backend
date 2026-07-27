from apps.common.permissions import PublicReadPermissionCode


class IsAdminOrAuthenticatedReadOnly(PublicReadPermissionCode):
    message = "You do not have permission to manage commodities."
