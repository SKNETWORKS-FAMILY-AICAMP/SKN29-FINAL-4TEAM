from django.urls import path
from .views import HealthView
urlpatterns = [path('', HealthView.as_view())]
