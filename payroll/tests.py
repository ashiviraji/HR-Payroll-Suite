
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Department, Employee
from payroll.models import (
    SalaryRecord,
    TaxBracket,
    PayrollRun,
    Payslip,
    TaxTable,
)


User = get_user_model()
Role = User._meta.get_field('role').remote_field.model


# =====================================================
# 1. UNAUTHENTICATED USER SECURITY TESTS
# =====================================================

class PayslipSecurityTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_user_cannot_access_payslips(self):

        response = self.client.get('/api/payslips/')

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ]
        )

    def test_unauthenticated_user_cannot_download_payslip(self):

        response = self.client.get(
            '/api/payslips/4/download/'
        )

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ]
        )


# =====================================================
# 2. EMPLOYEE PAYSLIP PERMISSION TESTS
# =====================================================

class PayslipPermissionTests(TestCase):

    def setUp(self):

        self.client = APIClient()

        # Create department
        self.department = Department.objects.create(
            name='IT Department'
        )

        # Create employee role
        self.employee_role = Role.objects.create(
            role_name='EMPLOYEE'
        )

        # Create line manager role
        self.manager_role = Role.objects.create(
            role_name='LINE_MANAGER'
        )

        # Create John employee record
        self.john_employee = Employee.objects.create(
            department=self.department,
            first_name='John',
            last_name='Employee',
            email='john.test@example.com',
            hire_date=date(2025, 1, 10),
            employment_status='ACTIVE'
        )

        # Create Sarah employee record
        self.sarah_employee = Employee.objects.create(
            department=self.department,
            first_name='Sarah',
            last_name='Manager',
            email='sarah.test@example.com',
            hire_date=date(2024, 6, 15),
            employment_status='ACTIVE'
        )

        # Create John user account
        self.john_user = User.objects.create_user(
            username='john',
            password='TestPassword123!',
            employee=self.john_employee,
            role=self.employee_role
        )

        # Create Sarah user account
        self.sarah_user = User.objects.create_user(
            username='sarah',
            password='TestPassword123!',
            employee=self.sarah_employee,
            role=self.manager_role
        )

        # Create tax table
        self.tax_table = TaxTable.objects.create(
            financial_year='2026-2027',
            effective_from=date(2026, 7, 1),
            effective_to=date(2027, 6, 30)
        )

        # Create payroll run
        self.payroll_run = PayrollRun.objects.create(
            tax_table=self.tax_table,
            period='2026-12',
            status='COMPLETED'
        )

        # Create John's payslip
        self.john_payslip = Payslip.objects.create(
            run=self.payroll_run,
            employee=self.john_employee,
            gross_pay=Decimal('6500.00'),
            tax_amount=Decimal('883.33'),
            total_deductions=Decimal('883.33'),
            net_pay=Decimal('5616.67'),
            pdf_path=''
        )

        # Create Sarah's payslip
        self.sarah_payslip = Payslip.objects.create(
            run=self.payroll_run,
            employee=self.sarah_employee,
            gross_pay=Decimal('7500.00'),
            tax_amount=Decimal('1083.33'),
            total_deductions=Decimal('1083.33'),
            net_pay=Decimal('6416.67'),
            pdf_path=''
        )

    # -------------------------------------------------
    # TEST 1: JOHN VIEWS HIS OWN PAYSLIP
    # -------------------------------------------------

    def test_john_can_view_own_payslip(self):

        self.client.force_authenticate(
            user=self.john_user
        )

        response = self.client.get(
            f'/api/payslips/{self.john_payslip.pk}/'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data['employee'],
            self.john_employee.pk
        )

    # -------------------------------------------------
    # TEST 2: JOHN CANNOT VIEW SARAH'S PAYSLIP
    # -------------------------------------------------

    def test_john_cannot_view_sarah_payslip(self):

        self.client.force_authenticate(
            user=self.john_user
        )

        response = self.client.get(
            f'/api/payslips/{self.sarah_payslip.pk}/'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    # -------------------------------------------------
    # TEST 3: SARAH DOWNLOADS HER OWN PDF
    # -------------------------------------------------

    def test_sarah_can_download_own_payslip(self):

        self.client.force_authenticate(
            user=self.sarah_user
        )

        response = self.client.get(
            f'/api/payslips/{self.sarah_payslip.pk}/download/'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response['Content-Type'],
            'application/pdf'
        )

        self.assertTrue(
            response.content.startswith(b'%PDF')
        )

    # -------------------------------------------------
    # TEST 4: JOHN CANNOT DOWNLOAD SARAH'S PDF
    # -------------------------------------------------

    def test_john_cannot_download_sarah_payslip(self):

        self.client.force_authenticate(
            user=self.john_user
        )

        response = self.client.get(
            f'/api/payslips/{self.sarah_payslip.pk}/download/'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )




# =====================================================
# 3. PAYROLL CALCULATION TESTS
# =====================================================

class PayrollCalculationTests(TestCase):

    def setUp(self):

        self.client = APIClient()

        # Create department
        self.department = Department.objects.create(
            name='IT Department'
        )

        # Create payroll administrator role
        self.payroll_role = Role.objects.create(
            role_name='PAYROLL_ADMIN'
        )

        # Create employee
        self.employee = Employee.objects.create(
            department=self.department,
            first_name='John',
            last_name='Employee',
            email='john.payroll@example.com',
            hire_date=date(2025, 1, 10),
            employment_status='ACTIVE'
        )

        # Create payroll administrator
        self.payroll_admin = User.objects.create_user(
            username='payroll_admin',
            password='TestPassword123!',
            role=self.payroll_role
        )

        # Create salary record
        self.salary_record = SalaryRecord.objects.create(
            employee=self.employee,
            base_salary=Decimal('78000.00'),
            effective_from=date(2026, 1, 1),
            effective_to=None
        )

        # Create tax table
        self.tax_table = TaxTable.objects.create(
            financial_year='2026-2027',
            effective_from=date(2026, 7, 1),
            effective_to=date(2027, 6, 30)
        )

        # Create simplified test tax brackets
        TaxBracket.objects.create(
            tax_table=self.tax_table,
            lower_bound=Decimal('0.00'),
            upper_bound=Decimal('20000.00'),
            rate=Decimal('0.00')
        )

        TaxBracket.objects.create(
            tax_table=self.tax_table,
            lower_bound=Decimal('20000.00'),
            upper_bound=Decimal('50000.00'),
            rate=Decimal('10.00')
        )

        TaxBracket.objects.create(
            tax_table=self.tax_table,
            lower_bound=Decimal('50000.00'),
            upper_bound=None,
            rate=Decimal('20.00')
        )

        # Create payroll run
        self.payroll_run = PayrollRun.objects.create(
            tax_table=self.tax_table,
            period='2026-12',
            status='PENDING'
        )

        # Authenticate as payroll administrator
        self.client.force_authenticate(
            user=self.payroll_admin
        )

    # -------------------------------------------------
    # TEST 1: PAYROLL PROCESSING
    # -------------------------------------------------

    def test_payroll_processing_creates_payslip(self):

        response = self.client.post(
            f'/api/payroll-runs/{self.payroll_run.pk}/process/'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertTrue(
            Payslip.objects.filter(
                run=self.payroll_run,
                employee=self.employee
            ).exists()
        )

    # -------------------------------------------------
    # TEST 2: MONTHLY GROSS SALARY
    # -------------------------------------------------

    def test_monthly_gross_salary_calculation(self):

        self.client.post(
            f'/api/payroll-runs/{self.payroll_run.pk}/process/'
        )

        payslip = Payslip.objects.get(
            run=self.payroll_run,
            employee=self.employee
        )

        # 78000 / 12 = 6500
        self.assertEqual(
            payslip.gross_pay,
            Decimal('6500.00')
        )

    # -------------------------------------------------
    # TEST 3: PROGRESSIVE TAX CALCULATION
    # -------------------------------------------------

    def test_progressive_tax_calculation(self):

        self.client.post(
            f'/api/payroll-runs/{self.payroll_run.pk}/process/'
        )

        payslip = Payslip.objects.get(
            run=self.payroll_run,
            employee=self.employee
        )

        # First 20000 at 0% = 0
        # Next 30000 at 10% = 3000
        # Remaining 28000 at 20% = 5600
        # Annual tax = 8600
        # Monthly tax = 716.67

        self.assertEqual(
            payslip.tax_amount,
            Decimal('716.67')
        )

    # -------------------------------------------------
    # TEST 4: NET SALARY CALCULATION
    # -------------------------------------------------

    def test_net_salary_calculation(self):

        self.client.post(
            f'/api/payroll-runs/{self.payroll_run.pk}/process/'
        )

        payslip = Payslip.objects.get(
            run=self.payroll_run,
            employee=self.employee
        )

        # Gross = 6500.00
        # Tax = 716.67
        # Net = 5783.33

        self.assertEqual(
            payslip.net_pay,
            Decimal('5783.33')
        )

        self.assertEqual(
            payslip.total_deductions,
            Decimal('716.67')
        )

    # -------------------------------------------------
    # TEST 5: DUPLICATE PAYROLL PROCESSING
    # -------------------------------------------------

    def test_duplicate_payroll_processing_is_rejected(self):

        url = (
            f'/api/payroll-runs/{self.payroll_run.pk}/process/'
        )

        first_response = self.client.post(url)

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK
        )

        second_response = self.client.post(url)

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertEqual(
            Payslip.objects.filter(
                run=self.payroll_run
            ).count(),
            1
        )





# =====================================================
# 4. PAYROLL ROLE-BASED PERMISSION TESTS
# =====================================================

class PayrollRolePermissionTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.department = Department.objects.create(
            name='Finance'
        )

        self.employee_role = Role.objects.create(
            role_name='EMPLOYEE'
        )

        self.manager_role = Role.objects.create(
            role_name='LINE_MANAGER'
        )

        self.payroll_role = Role.objects.create(
            role_name='PAYROLL_ADMIN'
        )

        self.employee = Employee.objects.create(
            department=self.department,
            first_name='John',
            last_name='Employee',
            email='john.role@example.com',
            hire_date=date(2025, 1, 10),
            employment_status='ACTIVE'
        )

        self.manager_employee = Employee.objects.create(
            department=self.department,
            first_name='Sarah',
            last_name='Manager',
            email='sarah.role@example.com',
            hire_date=date(2024, 6, 15),
            employment_status='ACTIVE'
        )

        self.john = User.objects.create_user(
            username='john_role_test',
            password='TestPassword123!',
            employee=self.employee,
            role=self.employee_role
        )

        self.sarah = User.objects.create_user(
            username='sarah_role_test',
            password='TestPassword123!',
            employee=self.manager_employee,
            role=self.manager_role
        )

        self.peter = User.objects.create_user(
            username='peter_role_test',
            password='TestPassword123!',
            role=self.payroll_role
        )

        self.tax_table = TaxTable.objects.create(
            financial_year='2026-2027',
            effective_from=date(2026, 7, 1),
            effective_to=date(2027, 6, 30)
        )

        self.payroll_run = PayrollRun.objects.create(
            tax_table=self.tax_table,
            period='2026-12',
            status='PENDING'
        )

        self.payslip = Payslip.objects.create(
            run=self.payroll_run,
            employee=self.employee,
            gross_pay=Decimal('6500.00'),
            tax_amount=Decimal('716.67'),
            total_deductions=Decimal('716.67'),
            net_pay=Decimal('5783.33'),
            pdf_path=''
        )

    def test_payroll_admin_can_create_payroll_run(self):
        self.client.force_authenticate(user=self.peter)

        response = self.client.post(
            '/api/payroll-runs/',
            {
                'tax_table': self.tax_table.pk,
                'period': '2027-01',
                'status': 'PENDING'
            },
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

    def test_employee_cannot_create_payroll_run(self):
        self.client.force_authenticate(user=self.john)

        response = self.client.post(
            '/api/payroll-runs/',
            {
                'tax_table': self.tax_table.pk,
                'period': '2027-01',
                'status': 'PENDING'
            },
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_manager_cannot_process_payroll(self):
        self.client.force_authenticate(user=self.sarah)

        response = self.client.post(
            f'/api/payroll-runs/{self.payroll_run.pk}/process/'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_payroll_admin_can_view_employee_payslip(self):
        self.client.force_authenticate(user=self.peter)

        response = self.client.get(
            f'/api/payslips/{self.payslip.pk}/'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

    def test_employee_cannot_modify_payslip(self):
        self.client.force_authenticate(user=self.john)

        response = self.client.patch(
            f'/api/payslips/{self.payslip.pk}/',
            {'net_pay': '9999.00'},
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED
        )

        self.payslip.refresh_from_db()

        self.assertEqual(
            self.payslip.net_pay,
            Decimal('5783.33')
        )
