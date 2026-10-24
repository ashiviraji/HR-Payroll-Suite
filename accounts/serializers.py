
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Role, UserAccount


# =========================================================
# ROLE SERIALIZER
# =========================================================

class RoleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Role
        fields = [
            'role_id',
            'role_name',
        ]
        read_only_fields = ['role_id']


# =========================================================
# USER ACCOUNT SERIALIZER
# =========================================================

class UserAccountSerializer(serializers.ModelSerializer):

    role_name = serializers.CharField(
        source='role.role_name',
        read_only=True,
        allow_null=True
    )

    employee_name = serializers.StringRelatedField(
        source='employee',
        read_only=True
    )

    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        style={'input_type': 'password'}
    )

    class Meta:
        model = UserAccount

        fields = [
            'user_id',
            'username',
            'email',
            'first_name',
            'last_name',
            'employee',
            'employee_name',
            'role',
            'role_name',
            'is_active',
            'password',
        ]

        read_only_fields = [
            'user_id',
        ]

    # -----------------------------------------------------
    # VALIDATE USER ACCOUNT
    # -----------------------------------------------------

    def validate(self, attrs):

        employee = attrs.get(
            'employee',
            self.instance.employee if self.instance else None
        )

        is_active = attrs.get(
            'is_active',
            self.instance.is_active if self.instance else True
        )

        # Prevent active accounts being linked to inactive employees
        if (
            employee is not None
            and employee.employment_status != 'ACTIVE'
            and is_active
        ):
            raise serializers.ValidationError({
                'employee':
                    'An active account cannot be linked to an inactive employee.'
            })

        # Prevent linking one employee to multiple accounts
        if employee is not None:
            existing_account = UserAccount.objects.filter(
                employee=employee
            )

            if self.instance:
                existing_account = existing_account.exclude(
                    pk=self.instance.pk
                )

            if existing_account.exists():
                raise serializers.ValidationError({
                    'employee':
                        'This employee is already linked to another user account.'
                })

        password = attrs.get('password')

        # Password required for new accounts
        if self.instance is None and not password:
            raise serializers.ValidationError({
                'password':
                    'Password is required when creating a user account.'
            })

        # Validate password strength
        if password is not None:

            if self.instance:
                user = self.instance
            else:
                user = UserAccount()

            user.username = attrs.get(
                'username',
                user.username
            )

            user.email = attrs.get(
                'email',
                user.email
            )

            try:
                validate_password(
                    password,
                    user=user
                )
            except DjangoValidationError as exc:
                raise serializers.ValidationError({
                    'password': list(exc.messages)
                })

        return attrs

    # -----------------------------------------------------
    # CREATE USER ACCOUNT
    # -----------------------------------------------------

    def create(self, validated_data):

        password = validated_data.pop('password')

        user = UserAccount.objects.create_user(
            password=password,
            **validated_data
        )

        return user

    # -----------------------------------------------------
    # UPDATE USER ACCOUNT
    # -----------------------------------------------------

    def update(self, instance, validated_data):

        password = validated_data.pop(
            'password',
            None
        )

        for field, value in validated_data.items():
            setattr(instance, field, value)

        if password is not None:
            instance.set_password(password)

        instance.save()

        return instance
