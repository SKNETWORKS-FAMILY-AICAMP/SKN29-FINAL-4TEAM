from django.urls import path
from .views import RegisterView, MeView
urlpatterns = [path('register/', RegisterView.as_view()), path('me/', MeView.as_view())]
