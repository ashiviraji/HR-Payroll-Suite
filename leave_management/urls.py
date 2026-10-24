
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    LeaveTypeViewSet,
    LeaveRequestViewSet,
    LeaveApprovalViewSet,
    LeaveAccrualViewSet,
    leave_balance,
)


router = DefaultRouter()

router.register(
    r'leave-types',
    LeaveTypeViewSet,
    basename='leave-type'
)

router.register(
    r'leave-requests',
    LeaveRequestViewSet,
    basename='leave-request'
)

router.register(
    r'leave-approvals',
    LeaveApprovalViewSet,
    basename='leave-approval'
)

router.register(
    r'leave-accruals',
    LeaveAccrualViewSet,
    basename='leave-accrual'
)


# Custom Leave Balance API
urlpatterns = [
    path(
        'leave-balance/',
        leave_balance,
        name='leave-balance'
    ),
]

# Include existing router URLs
urlpatterns += router.urls
