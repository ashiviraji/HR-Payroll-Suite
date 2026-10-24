from rest_framework.routers import DefaultRouter

from .views import (
    ReviewCycleViewSet,
    PerformanceReviewViewSet,
)


router = DefaultRouter()

router.register(
    r'review-cycles',
    ReviewCycleViewSet,
    basename='review-cycle'
)

router.register(
    r'performance-reviews',
    PerformanceReviewViewSet,
    basename='performance-review'
)


urlpatterns = router.urls