from rest_framework.routers import DefaultRouter

from .views import (
    SalaryRecordViewSet,
    TaxTableViewSet,
    TaxBracketViewSet,
    PayrollRunViewSet,
    PayslipViewSet,
)


router = DefaultRouter()

router.register(
    r'salary-records',
    SalaryRecordViewSet,
    basename='salary-record'
)

router.register(
    r'tax-tables',
    TaxTableViewSet,
    basename='tax-table'
)

router.register(
    r'tax-brackets',
    TaxBracketViewSet,
    basename='tax-bracket'
)

router.register(
    r'payroll-runs',
    PayrollRunViewSet,
    basename='payroll-run'
)

router.register(
    r'payslips',
    PayslipViewSet,
    basename='payslip'
)


urlpatterns = router.urls