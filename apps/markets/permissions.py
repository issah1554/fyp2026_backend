from apps.common.permissions import HasPermissionCode


class HasMarketPermission(HasPermissionCode):
    message = "You do not have permission to access markets."
