from rest_framework.permissions import BasePermission

from apps.auth.models import Profile


class IsOrderParticipant(BasePermission):
    message = "You do not have permission to view or manage this order."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff or user.is_superuser:
            return True
        try:
            if user.profile.role == Profile.Role.ADMIN:
                return True
        except Profile.DoesNotExist:
            pass

        # Buyer of the order or seller of the listing
        return obj.user == user or obj.listing.user == user
