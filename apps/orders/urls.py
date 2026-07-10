from django.urls import path

from .views import OrderDetailView, OrderListCreateView

app_name = "orders"

urlpatterns = [
    path("orders/", OrderListCreateView.as_view(), name="order-list"),
    path("orders/<str:order_id>/", OrderDetailView.as_view(), name="order-detail"),
]
