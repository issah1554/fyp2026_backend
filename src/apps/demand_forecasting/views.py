from django.core.paginator import EmptyPage, Paginator
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.common.responses import collection_response, error_response, mutation_response

from .models import DemandForecast, DemandForecastRun
from .serializers import DemandForecastRunSerializer, DemandForecastSerializer
from .services import latest_successful_run
from .training import train_and_forecast


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def paginated_response(request, queryset, serializer_class, extra_meta=None):
    page_number = positive_int(request.query_params.get("page"), 1)
    page_size = min(positive_int(request.query_params.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
    total_items = queryset.count()
    total_pages = max((total_items + page_size - 1) // page_size, 1)
    page_number = min(page_number, total_pages)
    paginator = Paginator(queryset, page_size)
    try:
        page = paginator.page(page_number)
    except EmptyPage:
        page = paginator.page(total_pages)

    meta = {
        "pagination": {
            "page": page.number,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
        }
    }
    if extra_meta:
        meta.update(extra_meta)
    return collection_response(serializer_class(page.object_list, many=True).data, meta=meta)


@extend_schema(tags=["Demand Forecasting"])
class DemandForecastListView(APIView):
    @extend_schema(responses={200: DemandForecastSerializer(many=True)})
    def get(self, request):
        run_id = request.query_params.get("run_id")
        commodity_id = request.query_params.get("commodity_id")
        adm_area_id = request.query_params.get("adm_area_id")
        week_from = request.query_params.get("week_from")
        week_to = request.query_params.get("week_to")

        run = DemandForecastRun.objects.filter(public_id=run_id).first() if run_id else latest_successful_run()
        if not run:
            return error_response(
                message="No completed demand forecast run found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        queryset = DemandForecast.objects.filter(run=run).select_related("run", "commodity", "adm_area")
        if commodity_id:
            queryset = queryset.filter(commodity__public_id=commodity_id)
        if adm_area_id:
            queryset = queryset.filter(adm_area__public_id=adm_area_id)
        if week_from:
            queryset = queryset.filter(week_start__gte=week_from)
        if week_to:
            queryset = queryset.filter(week_start__lte=week_to)

        return paginated_response(
            request,
            queryset,
            DemandForecastSerializer,
            extra_meta={
                "run": DemandForecastRunSerializer(run).data,
                "filters": {
                    "run_id": run_id or run.public_id,
                    "commodity_id": commodity_id or "",
                    "adm_area_id": adm_area_id or "",
                    "week_from": week_from or "",
                    "week_to": week_to or "",
                },
            },
        )


@extend_schema(tags=["Demand Forecasting"])
class DemandForecastRunListView(APIView):
    @extend_schema(responses={200: DemandForecastRunSerializer(many=True)})
    def get(self, request):
        queryset = DemandForecastRun.objects.all()
        return paginated_response(request, queryset, DemandForecastRunSerializer)


@extend_schema(tags=["Demand Forecasting"])
class DemandForecastTrainView(APIView):
    @extend_schema(responses={201: OpenApiResponse(description="Demand forecast training completed.")})
    def post(self, request):
        horizon_weeks = positive_int(request.data.get("horizon_weeks"), 4)
        estimators = positive_int(request.data.get("estimators"), 200)
        min_rows = positive_int(request.data.get("min_rows"), 200)
        result = train_and_forecast(
            horizon_weeks=horizon_weeks,
            estimators=estimators,
            min_rows=min_rows,
        )
        return mutation_response(
            message="Demand forecast training completed.",
            data=DemandForecastRunSerializer(result.run).data,
            status_code=status.HTTP_201_CREATED,
        )
