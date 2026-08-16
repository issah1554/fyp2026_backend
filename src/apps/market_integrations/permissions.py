from apps.common.permissions import HasPermissionCode


class HasMarketIntegrationPermission(HasPermissionCode):
    message = "You do not have permission to access market integrations."

    def has_permission(self, request, view):
        if not hasattr(view, "permission_codes"):
            view.permission_codes = {
                "GET": "market_integrations.read",
                "HEAD": "market_integrations.read",
                "OPTIONS": "market_integrations.read",
                "POST": "market_integrations.write",
                "PUT": "market_integrations.write",
                "PATCH": "market_integrations.write",
                "DELETE": "market_integrations.write",
            }
        return super().has_permission(request, view)
