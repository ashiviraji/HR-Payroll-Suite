
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    RoleViewSet,
    UserAccountViewSet,
)

router = DefaultRouter()

router.register(
    r'roles',
    RoleViewSet,
    basename='role'
)

router.register(
    r'users',
    UserAccountViewSet,
    basename='user-account'
)

urlpatterns = [
    path('', include(router.urls)),
]
