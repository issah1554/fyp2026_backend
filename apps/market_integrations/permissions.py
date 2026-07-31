from apps.common.permissions import PublicReadPermissionCode


class HasMarketIntegrationPermission(PublicReadPermissionCode):
    message = "You do not have permission to access market integrations."

    def has_permission(self, request, view):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return True
        return bool(request.user and request.user.is_authenticated)
