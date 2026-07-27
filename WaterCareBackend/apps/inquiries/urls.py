from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, InquiryViewSet
router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('inquiries', InquiryViewSet, basename='inquiry')
urlpatterns = router.urls
