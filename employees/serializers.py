
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Department, Employee


# =========================================================
# DEPARTMENT SERIALIZER
# =========================================================

class DepartmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Department
        fields = [
            'department_id',
            'name',
        ]
        read_only_fields = ['department_id']

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                'Department name cannot be empty.'
            )

        return value

    def validate(self, attrs):
        instance = Department(
            name=attrs.get(
                'name',
                self.instance.name if self.instance else ''
            )
        )

        if self.instance:
            instance.pk = self.instance.pk

        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict')
                else {'non_field_errors': exc.messages}
            )

        return attrs


# =========================================================
# EMPLOYEE SERIALIZER
# =========================================================

class EmployeeSerializer(serializers.ModelSerializer):

    department_name = serializers.CharField(
        source='department.name',
        read_only=True
    )

    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'employee_id',
            'first_name',
            'last_name',
            'email',
            'hire_date',
            'employment_status',
            'department',
            'department_name',
            'manager',
            'manager_name',
        ]

        read_only_fields = ['employee_id']

    def get_manager_name(self, obj):
        if obj.manager:
            return str(obj.manager)
        return None

    def validate_first_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                'First name cannot be empty.'
            )

        return value

    def validate_last_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                'Last name cannot be empty.'
            )

        return value

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        # Construct a temporary instance without modifying
        # the existing database record.
        if self.instance:
            employee = Employee(
                employee_id=self.instance.pk,
                first_name=self.instance.first_name,
                last_name=self.instance.last_name,
                email=self.instance.email,
                hire_date=self.instance.hire_date,
                employment_status=self.instance.employment_status,
                department=self.instance.department,
                manager=self.instance.manager,
            )
        else:
            employee = Employee()

        for field, value in attrs.items():
            setattr(employee, field, value)

        try:
            employee.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict')
                else {'non_field_errors': exc.messages}
            )

        return attrs
