
from django.urls import path
from . import web_views

urlpatterns = [

    # =====================================================
    # 1. PAYROLL RUNS LIST
    # =====================================================
    path(
        '',
        web_views.payroll_run_list,
        name='payroll_run_list'
    ),

    # =====================================================
    # 2. CREATE PAYROLL RUN
    # =====================================================
    path(
        'create/',
        web_views.payroll_run_create,
        name='payroll_run_create'
    ),

    # =====================================================
    # 3. PROCESS PAYROLL RUN
    # =====================================================
    path(
        '<int:run_id>/process/',
        web_views.payroll_run_process,
        name='payroll_run_process'
    ),

    # =====================================================
    # 4. VIEW GENERATED PAYSLIPS
    # =====================================================
    path(
        '<int:run_id>/payslips/',
        web_views.payroll_payslip_list,
        name='payroll_payslip_list'
    ),

]
