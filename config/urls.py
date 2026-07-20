"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.utils import timezone
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def root_view(_request):
    return JsonResponse(
        {
            "name": "SmartMarket API",
            "version": "1.0.0",
            "status": "online",
            "documentation": "/docs/",
            "openapi": "/openapi.json",
            "api": "/api/v1/",
            "timestamp": timezone.now().isoformat(),
        }
    )


urlpatterns = [
    path("", root_view, name="root"),
    path('admin/', admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("apps.auth.urls")),
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/commodities/", include("apps.commodities.urls")),
    path("api/v1/", include("apps.areas.urls")),
    path("api/v1/", include("apps.listings.urls")),
    path("api/v1/", include("apps.orders.urls")),
]
