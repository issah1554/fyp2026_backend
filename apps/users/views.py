from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.common.responses import collection_response, error_response, mutation_response, success_response

from .permissions import IsUserAdmin
from .serializers import ManagedUserCreateSerializer, ManagedUserSerializer, ManagedUserUpdateSerializer

User = get_user_model()


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
        users = self.get_queryset()
        return collection_response(ManagedUserSerializer(users, many=True).data)

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
