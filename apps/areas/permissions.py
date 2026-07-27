from apps.common.permissions import PublicReadPermissionCode


class IsAdminOrReadOnly(PublicReadPermissionCode):
    message = "You do not have permission to manage administrative areas."
