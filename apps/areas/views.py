from django.shortcuts import get_object_or_404
from django.db import IntegrityError, connection, transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.common.responses import collection_response, mutation_response, success_response

from .models import AdmArea
from .permissions import IsAdminOrReadOnly
from .serializers import AdmAreaPathImportSerializer, AdmAreaSerializer


AREA_PATH_LEVELS = [
    AdmArea.Level.REGION,
    AdmArea.Level.DISTRICT,
    AdmArea.Level.WARD,
]


def sync_adm_area_id_sequence():
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('adm_areas', 'id'),
                COALESCE((SELECT MAX(id) FROM adm_areas), 1),
                (SELECT COUNT(*) FROM adm_areas) > 0
            )
            """
        )


def get_area_by_path(path):
    parent = None
    area = None

    for index, name in enumerate(path):
        area = AdmArea.objects.filter(
            name=name,
            level=AREA_PATH_LEVELS[index],
            parent=parent,
        ).first()
        if area is None:
            return None
        parent = area

    return area


def create_area_path(path):
    parent = None
    area = None

    for index, name in enumerate(path):
        area, _created = AdmArea.objects.get_or_create(
            name=name,
            level=AREA_PATH_LEVELS[index],
            parent=parent,
        )
        parent = area

    return area


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
    @extend_schema(request=AdmAreaPathImportSerializer(many=True), responses={200: OpenApiResponse(description="Bulk import result.")})
    def post(self, request):
        serializer = AdmAreaPathImportSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        sync_adm_area_id_sequence()
        created = []
        skipped = []
        failed = []

        for index, item in enumerate(serializer.validated_data):
            path = item["path"]
            existing = get_area_by_path(path)
            if existing is not None:
                skipped.append(
                    {
                        "index": index,
                        "reason": "duplicate",
                        "message": "Area path already exists.",
                        "area": AdmAreaSerializer(existing).data,
                        "path": path,
                    }
                )
                continue

            try:
                with transaction.atomic():
                    created.append(create_area_path(path))
            except IntegrityError as exc:
                sync_adm_area_id_sequence()
                failed.append(
                    {
                        "index": index,
                        "reason": "integrity_error",
                        "message": str(exc),
                        "path": path,
                    }
                )

        result_status = status.HTTP_201_CREATED if created and not failed else status.HTTP_200_OK
        return mutation_response(
            message="Administrative area bulk import completed.",
            data={
                "created": AdmAreaSerializer(created, many=True).data,
                "skipped": skipped,
                "failed": failed,
            },
            meta={
                "created_count": len(created),
                "skipped_count": len(skipped),
                "failed_count": len(failed),
            },
            status_code=result_status,
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
