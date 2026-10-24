
from django.urls import path
from . import web_views


urlpatterns = [

    # =====================================================
    # EMPLOYEE LIST
    # =====================================================

    path(
        '',
        web_views.employee_list,
        name='employee_list'
    ),

    # =====================================================
    # CREATE EMPLOYEE
    # =====================================================

    path(
        'create/',
        web_views.employee_create,
        name='employee_create'
    ),

    # =====================================================
    # EMPLOYEE DETAILS
    # =====================================================

    path(
        '<int:pk>/',
        web_views.employee_detail,
        name='employee_detail'
    ),

    # =====================================================
    # EDIT EMPLOYEE
    # =====================================================

    path(
        '<int:pk>/edit/',
        web_views.employee_update,
        name='employee_update'
    ),

    # =====================================================
    # DEACTIVATE EMPLOYEE
    # =====================================================

    path(
        '<int:pk>/deactivate/',
        web_views.employee_deactivate,
        name='employee_deactivate'
    ),
]
