from django.contrib.auth import get_user_model
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.auth.models import Profile
from apps.common.responses import collection_response, error_response, mutation_response, success_response

from .permissions import IsUserAdmin
from .models import Permission, RolePermission
from .serializers import (
    ManagedUserCreateSerializer,
    ManagedUserSerializer,
    ManagedUserUpdateSerializer,
    PermissionSerializer,
    RolePermissionUpdateSerializer,
    RoleSerializer,
)

User = get_user_model()

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def user_totals():
    users = User.objects.select_related("profile")
    return {
        "total": users.count(),
        "active": users.filter(is_active=True).count(),
        "inactive": users.filter(is_active=False).count(),
        "admins": users.filter(profile__role=Profile.Role.ADMIN).count(),
        "verified": users.filter(profile__email_verified_at__isnull=False).count(),
    }


class UserAdminMixin:
    permission_classes = [IsUserAdmin]

    def get_queryset(self):
        return User.objects.select_related("profile").order_by("-date_joined")

    def get_user(self, user_id):
        return get_object_or_404(self.get_queryset(), profile__public_id=user_id)


@extend_schema(tags=["Users"])
class UserListCreateView(UserAdminMixin, APIView):
    @extend_schema(responses={200: ManagedUserSerializer(many=True)})
    def get(self, request):
        queryset = self.get_queryset()

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(profile__organization__icontains=search)
            )

        role = request.query_params.get("role")
        if role:
            queryset = queryset.filter(profile__role=role)

        is_active = request.query_params.get("is_active")
        if is_active in {"true", "false"}:
            queryset = queryset.filter(is_active=is_active == "true")

        page_number = positive_int(request.query_params.get("page"), 1)
        page_size = min(positive_int(request.query_params.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
        paginator = Paginator(queryset, page_size)

        try:
            page = paginator.page(page_number)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)

        return collection_response(
            ManagedUserSerializer(page.object_list, many=True).data,
            meta={
                "pagination": {
                    "page": page.number,
                    "page_size": page_size,
                    "total_items": paginator.count,
                    "total_pages": paginator.num_pages,
                    "has_next": page.has_next(),
                    "has_previous": page.has_previous(),
                },
                "filters": {
                    "role": role or "",
                    "is_active": is_active or "",
                },
                "sorting": {"ordering": "-date_joined"},
                "search": search or "",
                "totals": user_totals(),
            },
        )

    @extend_schema(request=ManagedUserCreateSerializer, responses={201: ManagedUserSerializer})
    def post(self, request):
        serializer = ManagedUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return mutation_response(
            message="User created successfully.",
            data=ManagedUserSerializer(user).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Users"])
class UserDetailView(UserAdminMixin, APIView):
    @extend_schema(responses={200: ManagedUserSerializer, 404: OpenApiResponse(description="User not found.")})
    def get(self, request, user_id):
        user = self.get_user(user_id)
        return success_response(ManagedUserSerializer(user).data)

    @extend_schema(request=ManagedUserUpdateSerializer, responses={200: ManagedUserSerializer})
    def patch(self, request, user_id):
        user = self.get_user(user_id)
        serializer = ManagedUserUpdateSerializer(user, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return mutation_response(
            message="User updated successfully.",
            data=ManagedUserSerializer(user).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="User deleted.")})
    def delete(self, request, user_id):
        user = self.get_user(user_id)
        if user == request.user:
            return error_response(
                message="You cannot delete your own account.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        user.delete()
        return mutation_response(message="User deleted successfully.", status_code=status.HTTP_200_OK)


def role_choices():
    return [{"value": value, "label": label} for value, label in Profile.Role.choices]


@extend_schema(tags=["Roles"])
class RoleListView(UserAdminMixin, APIView):
    @extend_schema(responses={200: RoleSerializer(many=True)})
    def get(self, request):
        return collection_response(RoleSerializer(role_choices(), many=True).data)


@extend_schema(tags=["Roles"])
class RoleDetailView(UserAdminMixin, APIView):
    @extend_schema(responses={200: RoleSerializer})
    def get(self, request, role_id):
        role = next((role for role in role_choices() if role["value"] == role_id), None)
        if role is None:
            return error_response(message="Role not found.", status_code=status.HTTP_404_NOT_FOUND)
        return success_response(RoleSerializer(role).data)

    @extend_schema(request=RolePermissionUpdateSerializer, responses={200: RoleSerializer})
    def patch(self, request, role_id):
        role = next((role for role in role_choices() if role["value"] == role_id), None)
        if role is None:
            return error_response(message="Role not found.", status_code=status.HTTP_404_NOT_FOUND)

        serializer = RolePermissionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permissions = Permission.objects.filter(public_id__in=serializer.validated_data["permission_ids"])

        RolePermission.objects.filter(role=role_id).delete()
        RolePermission.objects.bulk_create(
            [RolePermission(role=role_id, permission=permission) for permission in permissions],
            ignore_conflicts=True,
        )
        return mutation_response(
            message="Role permissions updated successfully.",
            data=RoleSerializer(role).data,
            status_code=status.HTTP_200_OK,
        )


@extend_schema(tags=["Permissions"])
class PermissionListCreateView(UserAdminMixin, APIView):
    @extend_schema(responses={200: PermissionSerializer(many=True)})
    def get(self, request):
        permissions = Permission.objects.all()
        search = request.query_params.get("search")
        if search:
            permissions = permissions.filter(Q(code__icontains=search) | Q(name__icontains=search))
        return collection_response(PermissionSerializer(permissions, many=True).data)


@extend_schema(tags=["Permissions"])
class PermissionDetailView(UserAdminMixin, APIView):
    def get_permission(self, permission_id):
        return get_object_or_404(Permission.objects.all(), public_id=permission_id)

    @extend_schema(responses={200: PermissionSerializer, 404: OpenApiResponse(description="Permission not found.")})
    def get(self, request, permission_id):
        return success_response(PermissionSerializer(self.get_permission(permission_id)).data)
