from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.common.responses import collection_response, mutation_response, success_response

from .models import AdmArea
from .permissions import IsAdminOrReadOnly
from .serializers import AdmAreaSerializer


class AdmAreaMixin:
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        return AdmArea.objects.all()

    def get_area(self, area_id):
        return get_object_or_404(self.get_queryset(), public_id=area_id)


@extend_schema(tags=["Administrative Areas"])
class AdmAreaListCreateView(AdmAreaMixin, APIView):
    @extend_schema(responses={200: AdmAreaSerializer(many=True)})
    def get(self, request):
        queryset = self.get_queryset()

        level = request.query_params.get("level")
        if level:
            queryset = queryset.filter(level=level)

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search)

        parent_id = request.query_params.get("parent_id")
        if parent_id:
            queryset = queryset.filter(parent__public_id=parent_id)

        return collection_response(AdmAreaSerializer(queryset, many=True).data)

    @extend_schema(request=AdmAreaSerializer, responses={201: AdmAreaSerializer})
    def post(self, request):
        serializer = AdmAreaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        area = serializer.save()
        return mutation_response(
            message="Administrative area created successfully.",
            data=AdmAreaSerializer(area).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Administrative Areas"])
class AdmAreaBulkCreateView(AdmAreaMixin, APIView):
    @extend_schema(request=AdmAreaSerializer(many=True), responses={201: AdmAreaSerializer(many=True)})
    def post(self, request):
        serializer = AdmAreaSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        areas = serializer.save()
        return mutation_response(
            message="Administrative areas created successfully.",
            data=AdmAreaSerializer(areas, many=True).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Administrative Areas"])
class AdmAreaDetailView(AdmAreaMixin, APIView):
    @extend_schema(responses={200: AdmAreaSerializer, 404: OpenApiResponse(description="Area not found.")})
    def get(self, request, area_id):
        area = self.get_area(area_id)
        return success_response(AdmAreaSerializer(area).data)

    @extend_schema(request=AdmAreaSerializer, responses={200: AdmAreaSerializer})
    def patch(self, request, area_id):
        area = self.get_area(area_id)
        serializer = AdmAreaSerializer(area, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        area = serializer.save()
        return mutation_response(
            message="Administrative area updated successfully.",
            data=AdmAreaSerializer(area).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="Area deleted.")})
    def delete(self, request, area_id):
        area = self.get_area(area_id)
        area.delete()
        return mutation_response(message="Administrative area deleted successfully.", status_code=status.HTTP_200_OK)
