
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Sum
from django.urls import path, include
from django.views.generic import TemplateView

from employees.models import Employee
from leave_management.models import LeaveRequest, LeaveAccrual
from leave_management.services import get_available_leave_hours
from payroll.models import PayrollRun, Payslip, SalaryRecord
from performance.models import PerformanceReview


# =========================================================
# DASHBOARD VIEW
# =========================================================

class DashboardView(LoginRequiredMixin, TemplateView):

    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        user = self.request.user

        role_name = (
            user.role.role_name
            if user.role_id is not None
            else None
        )

        # =================================================
        # ROLE PERMISSIONS
        # =================================================

        is_hr = (
            user.is_superuser
            or role_name == 'HR_OFFICER'
        )

        is_payroll_admin = (
            user.is_superuser
            or role_name == 'PAYROLL_ADMIN'
        )

        is_line_manager = (
            role_name == 'LINE_MANAGER'
            and not user.is_superuser
        )

        is_employee = (
            role_name == 'EMPLOYEE'
            and not user.is_superuser
        )

        context['can_view_hr_stats'] = is_hr
        context['can_view_payroll_stats'] = is_payroll_admin
        context['can_view_manager_stats'] = is_line_manager
        context['can_view_employee_stats'] = is_employee

        # =================================================
        # HR OFFICER DASHBOARD
        # =================================================

        if is_hr:

            context['total_employees'] = (
                Employee.objects.count()
            )

            context['active_employees'] = (
                Employee.objects.filter(
                    employment_status='ACTIVE'
                ).count()
            )

            context['pending_leaves'] = (
                LeaveRequest.objects.filter(
                    status='PENDING'
                ).count()
            )

            context['awaiting_hr_approval'] = (
                LeaveRequest.objects.filter(
                    status='MANAGER_APPROVED'
                ).count()
            )

            context['approved_leaves'] = (
                LeaveRequest.objects.filter(
                    status='APPROVED'
                ).count()
            )


            # HR workflow: only manager-approved requests are ready
            # for the HR Officer's final approval stage.
            context['hr_approval_queue'] = (
                LeaveRequest.objects.filter(status='MANAGER_APPROVED')
                .select_related('employee', 'leave_type')
                .order_by('start_date', 'request_id')[:6]
            )
            context['recent_employees'] = (
                Employee.objects.select_related('department', 'manager')
                .order_by('-hire_date', '-employee_id')[:6]
            )
            context['inactive_employees'] = Employee.objects.filter(
                employment_status='INACTIVE'
            ).count()
            context['terminated_employees'] = Employee.objects.filter(
                employment_status='TERMINATED'
            ).count()
            context['total_leave_requests'] = LeaveRequest.objects.count()

        # =================================================
        # PAYROLL ADMIN DASHBOARD
        # =================================================

        if is_payroll_admin:

            payroll_runs = PayrollRun.objects.all()
            completed_runs = payroll_runs.filter(status='COMPLETED')
            completed_payslips = Payslip.objects.filter(
                run__status='COMPLETED'
            )

            totals = completed_payslips.aggregate(
                gross=Sum('gross_pay'),
                net=Sum('net_pay'),
                tax=Sum('tax_amount'),
                deductions=Sum('total_deductions'),
            )

            context.update({
                # Keep the original context variable for existing templates.
                'payroll_runs': payroll_runs.count(),
                'pending_payroll_runs': payroll_runs.filter(
                    status='PENDING'
                ).count(),
                'processing_payroll_runs': payroll_runs.filter(
                    status='PROCESSING'
                ).count(),
                'completed_payroll_runs': completed_runs.count(),
                'failed_payroll_runs': payroll_runs.filter(
                    status='FAILED'
                ).count(),
                # Only completed payroll is included in financial totals.
                'payroll_total_gross': totals['gross'] or Decimal('0.00'),
                'payroll_total_net': totals['net'] or Decimal('0.00'),
                'payroll_total_tax': totals['tax'] or Decimal('0.00'),
                'payroll_total_deductions': totals['deductions'] or Decimal('0.00'),
                'payslips_generated': completed_payslips.count(),
                'pending_payroll_queue': (
                    payroll_runs.filter(status='PENDING')
                    .select_related('tax_table')
                    .order_by('period', 'run_id')[:5]
                ),
                'recent_payroll_runs': (
                    payroll_runs.select_related('tax_table')
                    .order_by('-period', '-run_id')[:6]
                ),
                'latest_completed_payroll': (
                    completed_runs.order_by('-period', '-run_id').first()
                ),
            })

        # =================================================
        # LINE MANAGER DASHBOARD
        # =================================================

        if is_line_manager:

            # Default values
            context.update({
                'manager_profile': None,
                'team_members': 0,
                'team_directory': [],
                'pending_team_leaves': 0,
                'pending_team_leave_list': [],
                'team_average_rating': None,
                'team_review_count': 0,
                'recent_team_reviews': [],
            })

            if user.employee_id is not None:

                # -----------------------------------------
                # MANAGER PROFILE
                # -----------------------------------------

                manager = (
                    Employee.objects
                    .select_related('department')
                    .get(pk=user.employee_id)
                )

                context['manager_profile'] = manager

                # -----------------------------------------
                # TEAM MEMBERS
                # -----------------------------------------

                team = (
                    Employee.objects.filter(
                        manager_id=manager.employee_id
                    )
                    .select_related('department')
                )

                context['team_members'] = team.count()

                context['team_directory'] = (
                    team.order_by(
                        'first_name',
                        'last_name'
                    )
                )

                # -----------------------------------------
                # PENDING TEAM LEAVE REQUESTS
                # -----------------------------------------

                pending_requests = (
                    LeaveRequest.objects.filter(
                        employee__in=team,
                        status='PENDING'
                    )
                    .select_related(
                        'employee',
                        'leave_type'
                    )
                    .order_by(
                        'start_date',
                        'request_id'
                    )
                )

                context['pending_team_leaves'] = (
                    pending_requests.count()
                )

                context['pending_team_leave_list'] = (
                    pending_requests[:5]
                )

                # -----------------------------------------
                # TEAM PERFORMANCE STATISTICS
                # -----------------------------------------

                reviews = (
                    PerformanceReview.objects.filter(
                        employee__in=team
                    )
                )

                context['team_average_rating'] = (
                    reviews.aggregate(
                        average=Avg('rating')
                    )['average']
                )

                context['team_review_count'] = (
                    reviews.count()
                )

                # -----------------------------------------
                # RECENT TEAM PERFORMANCE REVIEWS
                # -----------------------------------------

                context['recent_team_reviews'] = (
                    reviews.select_related(
                        'employee',
                        'reviewer',
                        'cycle'
                    )
                    .order_by(
                        '-review_date',
                        '-review_id'
                    )[:5]
                )

        # =================================================
        # EMPLOYEE DASHBOARD
        # =================================================

        if is_employee:

            # Default values
            context.update({
                'employee_profile': None,
                'annual_leave_hours': None,
                'annual_leave_days': None,
                'latest_payslip': None,
                'current_salary': None,
                'latest_review': None,
                'pending_own_leaves': 0,
                'approved_own_leaves': 0,
                'rejected_own_leaves': 0,
                'salary_chart_labels': [],
                'salary_chart_values': [],
            })

            if user.employee_id is not None:

                # -----------------------------------------
                # EMPLOYEE PROFILE
                # -----------------------------------------

                employee = (
                    Employee.objects
                    .select_related(
                        'department',
                        'manager'
                    )
                    .get(pk=user.employee_id)
                )

                context['employee_profile'] = employee

                # -----------------------------------------
                # ANNUAL LEAVE ACCRUAL
                # -----------------------------------------

                annual_accruals = (
                    LeaveAccrual.objects.filter(
                        employee=employee,
                        leave_type__name='Annual Leave'
                    )
                )

                accrued = (
                    annual_accruals.aggregate(
                        total=Sum('hours_accrued')
                    )['total']
                )

                # Display the available balance, not the accrued total.
                # PENDING, MANAGER_APPROVED and APPROVED reduce availability;
                # REJECTED requests are excluded and restore availability.
                annual_accrual = annual_accruals.select_related('leave_type').first()
                available_hours = (
                    get_available_leave_hours(employee, annual_accrual.leave_type)
                    if annual_accrual is not None
                    else None
                )
                context['annual_leave_hours'] = available_hours
                context['annual_leave_days'] = (
                    available_hours / Decimal('7.6')
                    if available_hours is not None
                    else None
                )

                # -----------------------------------------
                # EMPLOYEE LEAVE STATISTICS
                # -----------------------------------------

                leaves = (
                    LeaveRequest.objects.filter(
                        employee=employee
                    )
                )

                context['pending_own_leaves'] = (
                    leaves.filter(
                        status='PENDING'
                    ).count()
                )

                context['approved_own_leaves'] = (
                    leaves.filter(
                        status='APPROVED'
                    ).count()
                )

                context['rejected_own_leaves'] = (
                    leaves.filter(
                        status='REJECTED'
                    ).count()
                )

                # -----------------------------------------
                # CURRENT SALARY
                # -----------------------------------------

                context['current_salary'] = (
                    SalaryRecord.objects.filter(
                        employee=employee
                    )
                    .order_by(
                        '-effective_from',
                        '-salary_id'
                    )
                    .first()
                )

                # -----------------------------------------
                # COMPLETED PAYSLIPS
                # -----------------------------------------

                payslips = (
                    Payslip.objects.filter(
                        employee=employee,
                        run__status='COMPLETED'
                    )
                    .select_related('run')
                    .order_by(
                        '-run__period',
                        '-payslip_id'
                    )
                )

                context['latest_payslip'] = (
                    payslips.first()
                )

                # -----------------------------------------
                # SALARY EARNINGS CHART
                # -----------------------------------------

                recent_payslips = list(
                    payslips[:6]
                )

                recent_payslips.reverse()

                context['salary_chart_labels'] = [
                    payslip.run.period
                    for payslip in recent_payslips
                ]

                context['salary_chart_values'] = [
                    float(payslip.net_pay)
                    for payslip in recent_payslips
                ]

                # -----------------------------------------
                # LATEST PERFORMANCE REVIEW
                # -----------------------------------------

                context['latest_review'] = (
                    PerformanceReview.objects.filter(
                        employee=employee
                    )
                    .select_related(
                        'reviewer',
                        'cycle'
                    )
                    .order_by(
                        '-review_date',
                        '-review_id'
                    )
                    .first()
                )

        return context


# =========================================================
# URL CONFIGURATION
# =========================================================

urlpatterns = [

    # =====================================================
    # 1. DJANGO ADMIN
    # =====================================================

    path(
        'admin/',
        admin.site.urls
    ),

    # =====================================================
    # 2. DASHBOARD
    # =====================================================

    path(
        '',
        DashboardView.as_view(),
        name='dashboard'
    ),

    # =====================================================
    # 3. AUTHENTICATION
    # =====================================================

    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
            redirect_authenticated_user=True
        ),
        name='login'
    ),

    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout'
    ),

    # =====================================================
    # 4. HTML USER INTERFACE ROUTES
    # =====================================================

    path(
        'employees/',
        include('employees.web_urls')
    ),

    path(
        'performance/',
        include('performance.web_urls')
    ),

    path(
        'leave/',
        include('leave_management.web_urls')
    ),

    path(
        'payroll/',
        include('payroll.web_urls')
    ),

    path(
        'notifications/',
        include('notifications.urls')
    ),

    # Audit Logs HTML page (HR Officers and superusers)
    path(
        'audit-logs/',
        include('audit.web_urls')
    ),

    # User Accounts HTML page (HR Officers and superusers)
    path(
        'user-accounts/',
        include('accounts.web_urls')
    ),

    # =====================================================
    # 5. REST API ROUTES
    # =====================================================

    path(
        'api/',
        include('employees.urls')
    ),

    path(
        'api/',
        include('leave_management.urls')
    ),

    path(
        'api/',
        include('performance.urls')
    ),

    path(
        'api/',
        include('payroll.urls')
    ),

    path(
        'api/',
        include('audit.urls')
    ),

    path(
        'api/accounts/',
        include('accounts.urls')
    ),

    # =====================================================
    # 6. DJANGO REST FRAMEWORK AUTHENTICATION
    # =====================================================

    path(
        'api-auth/',
        include('rest_framework.urls')
    ),

]
