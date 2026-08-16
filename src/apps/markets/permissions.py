from apps.common.permissions import PublicReadPermissionCode


class HasMarketPermission(PublicReadPermissionCode):
    message = "You do not have permission to access markets."
