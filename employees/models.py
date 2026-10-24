
from django.db import models
from django.core.exceptions import ValidationError


# =========================================================
# DEPARTMENT MODEL
# =========================================================

class Department(models.Model):
    department_id = models.AutoField(primary_key=True)

    name = models.CharField(
        max_length=100,
        unique=True
    )

    def clean(self):
        super().clean()

        if self.name:
            self.name = self.name.strip()

            if not self.name:
                raise ValidationError({
                    'name': 'Department name cannot be empty.'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# =========================================================
# EMPLOYEE MODEL
# =========================================================

class Employee(models.Model):

    EMPLOYMENT_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('TERMINATED', 'Terminated'),
    ]

    employee_id = models.AutoField(primary_key=True)

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='employees'
    )

    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports'
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    email = models.EmailField(unique=True)

    hire_date = models.DateField()

    employment_status = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_STATUS_CHOICES,
        default='ACTIVE'
    )

    # -----------------------------------------------------
    # MODEL VALIDATION
    # -----------------------------------------------------

    def clean(self):
        super().clean()

        if self.first_name:
            self.first_name = self.first_name.strip()

        if self.last_name:
            self.last_name = self.last_name.strip()

        if not self.first_name:
            raise ValidationError({
                'first_name': 'First name cannot be empty.'
            })

        if not self.last_name:
            raise ValidationError({
                'last_name': 'Last name cannot be empty.'
            })

        # Validate manager assignment
        if self.manager_id is not None:

            if (
                self.pk is not None
                and self.manager_id == self.pk
            ):
                raise ValidationError({
                    'manager':
                        'An employee cannot be their own manager.'
                })

            # Prevent circular reporting relationships
            visited = set()

            if self.pk is not None:
                visited.add(self.pk)

            current_manager_id = self.manager_id

            while current_manager_id is not None:

                if current_manager_id in visited:
                    raise ValidationError({
                        'manager':
                            'Circular reporting relationships are not allowed.'
                    })

                visited.add(current_manager_id)

                current_manager_id = (
                    Employee.objects.filter(
                        pk=current_manager_id
                    ).values_list(
                        'manager_id',
                        flat=True
                    ).first()
                )

    # -----------------------------------------------------
    # SAVE WITH VALIDATION
    # -----------------------------------------------------

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
