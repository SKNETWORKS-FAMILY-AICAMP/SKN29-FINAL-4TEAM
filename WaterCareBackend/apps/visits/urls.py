from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DrivingRouteView, VisitRequestViewSet

router = DefaultRouter()
router.register("visits", VisitRequestViewSet, basename="visit")

urlpatterns = [
    path(
        "routes/driving/",
        DrivingRouteView.as_view(),
        name="driving-route",
    ),
] + router.urls
