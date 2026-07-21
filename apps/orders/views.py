from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.auth.models import Profile
from apps.common.responses import collection_response, mutation_response, success_response
from .models import Order
from .permissions import IsOrderParticipant
from .serializers import OrderSerializer


class OrderMixin:
    permission_classes = [IsOrderParticipant]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Order.objects.none()
            
        # Admin / staff see everything
        if user.is_staff or user.is_superuser:
            return Order.objects.select_related("listing__commodity", "listing__adm_area", "user__profile").all()
            
        try:
            if user.profile.role.code == Profile.Role.ADMIN:
                return Order.objects.select_related("listing__commodity", "listing__adm_area", "user__profile", "user__profile__role").all()
        except Profile.DoesNotExist:
            pass

        # Regular user sees orders they placed, or orders for listings they own
        return Order.objects.select_related("listing__commodity", "listing__adm_area", "user__profile").filter(
            user=user
        ) | Order.objects.select_related("listing__commodity", "listing__adm_area", "user__profile").filter(
            listing__user=user
        )

    def get_order(self, order_id):
        order = get_object_or_404(
            Order.objects.select_related("listing__commodity", "listing__adm_area", "user__profile").all(),
            public_id=order_id
        )
        self.check_object_permissions(self.request, order)
        return order


@extend_schema(tags=["Orders"])
class OrderListCreateView(OrderMixin, APIView):
    permission_codes = {
        "GET": "orders.list",
        "POST": "orders.create",
    }

    @extend_schema(responses={200: OrderSerializer(many=True)})
    def get(self, request):
        orders = self.get_queryset()
        return collection_response(OrderSerializer(orders, many=True).data)

    @extend_schema(request=OrderSerializer, responses={201: OrderSerializer})
    def post(self, request):
        serializer = OrderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return mutation_response(
            message="Order placed successfully.",
            data=OrderSerializer(order).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Orders"])
class OrderDetailView(OrderMixin, APIView):
    permission_codes = {
        "GET": "orders.read",
        "PATCH": "orders.update",
    }

    @extend_schema(responses={200: OrderSerializer, 404: OpenApiResponse(description="Order not found.")})
    def get(self, request, order_id):
        order = self.get_order(order_id)
        return success_response(OrderSerializer(order).data)

    @extend_schema(request=OrderSerializer, responses={200: OrderSerializer})
    def patch(self, request, order_id):
        order = self.get_order(order_id)
        
        # Validation on status transitions can be added here if needed
        serializer = OrderSerializer(order, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return mutation_response(
            message="Order updated successfully.",
            data=OrderSerializer(order).data,
            status_code=status.HTTP_200_OK,
        )
