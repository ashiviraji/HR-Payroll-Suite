
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import (
    urlsafe_base64_decode,
    urlsafe_base64_encode,
)
from django.views.decorators.http import require_http_methods

from employees.models import Employee

from .models import Role
from .serializers import UserAccountSerializer
from .tokens import account_invitation_token


logger = logging.getLogger(__name__)
User = get_user_model()


# =========================================================
# ACCOUNT MANAGEMENT PERMISSIONS
# =========================================================

def can_manage_accounts(user):
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return (
        user.role_id is not None
        and user.role.role_name == 'HR_OFFICER'
    )


# =========================================================
# SEND ACCOUNT INVITATION EMAIL
# =========================================================

def send_account_invitation(request, account):
    """
    Send a secure password-setup invitation.

    The account must remain inactive until the employee
    successfully sets a password.
    """

    if account.is_active:
        raise ValueError(
            "Invitations can only be sent to inactive accounts."
        )

    if not account.email:
        raise ValueError(
            "The user account does not have an email address."
        )

    uid = urlsafe_base64_encode(
        force_bytes(account.pk)
    )

    token = account_invitation_token.make_token(account)

    activation_url = request.build_absolute_uri(
        reverse(
            'user_account_activate',
            kwargs={
                'uidb64': uid,
                'token': token,
            }
        )
    )

    subject = "HR Payroll System - Set Up Your Account"

    message = (
        f"Hello {account.first_name or account.username},\n\n"
        "An account has been created for you in the "
        "HR Payroll System.\n\n"
        "Please use the following link to set your password "
        "and activate your account:\n\n"
        f"{activation_url}\n\n"
        "This invitation expires after 24 hours.\n\n"
        "If you were not expecting this invitation, "
        "please contact your HR Officer.\n\n"
        "HR Payroll System"
    )

    # Read the configured sender explicitly. Never send with an empty address.
    sender_email = (
        getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        or getattr(settings, 'EMAIL_HOST_USER', '')
    ).strip()

    if not sender_email:
        raise ValueError(
            'Gmail sender address is missing. '
            'Set EMAIL_HOST_USER in the project-root .env file '
            'and restart the Django server.'
        )

    if not getattr(settings, 'EMAIL_HOST_PASSWORD', ''):
        raise ValueError(
            'Gmail App Password is missing. '
            'Set EMAIL_HOST_PASSWORD in the project-root .env file '
            'and restart the Django server.'
        )

    sent_count = send_mail(
        subject=subject,
        message=message,
        from_email=sender_email,
        recipient_list=[account.email],
        fail_silently=False,
    )

    if sent_count != 1:
        raise RuntimeError("The invitation email was not accepted by the email backend.")

    logger.info("Account invitation accepted for user ID %s", account.pk)
    return sent_count


# =========================================================
# USER ACCOUNT LIST
# =========================================================

@login_required
def user_account_list(request):

    if not can_manage_accounts(request.user):
        raise PermissionDenied(
            "You do not have permission to manage user accounts."
        )

    user_accounts = (
        User.objects
        .select_related('role', 'employee')
        .order_by('username')
    )

    return render(
        request,
        'accounts/user_account_list.html',
        {
            'user_accounts': user_accounts
        }
    )


# =========================================================
# CREATE USER ACCOUNT
# =========================================================

@login_required
@require_http_methods(["GET", "POST"])
def user_account_create(request):

    if not can_manage_accounts(request.user):
        raise PermissionDenied(
            "You do not have permission to create user accounts."
        )

    roles = Role.objects.all().order_by('role_name')

    available_employees = (
        Employee.objects
        .filter(
            employment_status='ACTIVE',
            user_account__isnull=True
        )
        .order_by('first_name', 'last_name')
    )

    if request.method == 'POST':

        employee_id = request.POST.get(
            'employee', ''
        ).strip()

        username = request.POST.get(
            'username', ''
        ).strip()

        role_id = request.POST.get(
            'role', ''
        ).strip()

        employee = None

        if employee_id.isdigit():
            employee = Employee.objects.filter(
                pk=employee_id,
                employment_status='ACTIVE',
                user_account__isnull=True
            ).first()

        if employee is None:
            messages.error(
                request,
                "Please select an active employee "
                "without an existing account."
            )

        elif not employee.email:
            messages.error(
                request,
                "The selected employee must have "
                "a valid email address."
            )

        else:

            # Temporary random password satisfies serializer validation.
            # The account is saved with an unusable password.
            from django.utils.crypto import get_random_string

            data = {
                'employee': employee.pk,
                'username': username,
                'first_name': employee.first_name,
                'last_name': employee.last_name,
                'email': employee.email,
                'role': role_id,
                'is_active': False,
                'password': get_random_string(32),
            }

            serializer = UserAccountSerializer(
                data=data
            )

            if serializer.is_valid():

                try:
                    with transaction.atomic():

                        account = serializer.save()

                        # Prevent login until password setup
                        account.set_unusable_password()
                        account.is_active = False
                        account.save(
                            update_fields=[
                                'password',
                                'is_active',
                            ]
                        )

                except IntegrityError:
                    messages.error(
                        request,
                        "Unable to create the account. "
                        "The username or employee may "
                        "already be linked to another account."
                    )

                else:
                    try:
                        send_account_invitation(
                            request,
                            account
                        )

                    except Exception:
                        logger.exception(
                            "Failed to send account invitation "
                            "for user ID %s.",
                            account.pk
                        )

                        messages.warning(
                            request,
                            (
                                f"Account '{account.username}' "
                                "was created, but the invitation "
                                "email could not be sent. "
                                "The account remains inactive."
                            )
                        )

                    else:
                        messages.success(
                            request,
                            (
                                f"Account '{account.username}' "
                                "created successfully. "
                                "A password-setup invitation "
                                "was accepted for delivery to "
                                f"{account.email}."
                            )
                        )

                    return redirect(
                        'user_account_list'
                    )

            else:
                for field, errors in serializer.errors.items():
                    for error in errors:
                        messages.error(
                            request,
                            f"{field}: {error}"
                        )

    return render(
        request,
        'accounts/user_account_create.html',
        {
            'roles': roles,
            'available_employees': available_employees,
        }
    )


# =========================================================
# ACTIVATE ACCOUNT AND SET PASSWORD
# =========================================================

@require_http_methods(["GET", "POST"])
def user_account_activate(request, uidb64, token):
    """
    Validate the invitation and let the employee
    set a password before activating the account.
    """

    try:
        user_id = force_str(
            urlsafe_base64_decode(uidb64)
        )

        account = User.objects.select_related(
            'employee'
        ).get(pk=user_id)

    except (
        ValueError,
        TypeError,
        OverflowError,
        User.DoesNotExist,
    ):
        account = None

    invitation_valid = (
        account is not None
        and not account.is_active
        and account.employee_id is not None
        and account.employee.employment_status == 'ACTIVE'
        and account_invitation_token.check_token(
            account,
            token
        )
    )

    if not invitation_valid:
        return render(
            request,
            'accounts/user_account_activate.html',
            {
                'valid_link': False,
            }
        )

    if request.method == 'POST':

        password1 = request.POST.get(
            'password1', ''
        )

        password2 = request.POST.get(
            'password2', ''
        )

        if password1 != password2:
            messages.error(
                request,
                "The passwords do not match."
            )

        else:
            try:
                validate_password(
                    password1,
                    user=account
                )

            except ValidationError as exc:
                for error in exc.messages:
                    messages.error(
                        request,
                        error
                    )

            else:
                with transaction.atomic():

                    # Lock and recheck before activation
                    locked_account = (
                        User.objects
                        .select_for_update()
                        .select_related('employee')
                        .get(pk=account.pk)
                    )

                    still_valid = (
                        not locked_account.is_active
                        and locked_account.employee_id is not None
                        and locked_account.employee.employment_status
                        == 'ACTIVE'
                        and account_invitation_token.check_token(
                            locked_account,
                            token
                        )
                    )

                    if not still_valid:
                        return render(
                            request,
                            'accounts/user_account_activate.html',
                            {
                                'valid_link': False,
                            }
                        )

                    locked_account.set_password(
                        password1
                    )

                    locked_account.is_active = True

                    locked_account.save(
                        update_fields=[
                            'password',
                            'is_active',
                        ]
                    )

                messages.success(
                    request,
                    "Your account has been activated. "
                    "You can now log in."
                )

                return redirect('login')

    return render(
        request,
        'accounts/user_account_activate.html',
        {
            'valid_link': True,
            'account': account,
        }
    )


# =========================================================
# EDIT USER ACCOUNT
# =========================================================

@login_required
@require_http_methods(["GET", "POST"])
def user_account_edit(request, user_id):

    if not can_manage_accounts(request.user):
        raise PermissionDenied(
            "You do not have permission to edit user accounts."
        )

    account = get_object_or_404(
        User.objects.select_related('role', 'employee'),
        pk=user_id
    )

    if account.is_superuser:
        raise PermissionDenied(
            "Superuser accounts cannot be edited from this page."
        )

    roles = Role.objects.all().order_by('role_name')

    if request.method == 'POST':

        data = {
            'username': request.POST.get(
                'username', ''
            ).strip(),

            'first_name': request.POST.get(
                'first_name', ''
            ).strip(),

            'last_name': request.POST.get(
                'last_name', ''
            ).strip(),

            'email': request.POST.get(
                'email', ''
            ).strip(),

            'role': request.POST.get(
                'role', ''
            ),
        }

        serializer = UserAccountSerializer(
            account,
            data=data,
            partial=True
        )

        if serializer.is_valid():

            with transaction.atomic():

                updated_account = serializer.save()

                # Synchronize linked Employee information
                if updated_account.employee_id:

                    employee = updated_account.employee

                    update_fields = []

                    if employee.email != updated_account.email:
                        employee.email = updated_account.email
                        update_fields.append('email')

                    if employee.first_name != updated_account.first_name:
                        employee.first_name = updated_account.first_name
                        update_fields.append('first_name')

                    if employee.last_name != updated_account.last_name:
                        employee.last_name = updated_account.last_name
                        update_fields.append('last_name')

                    if update_fields:
                        employee.save(
                            update_fields=update_fields
                        )

            messages.success(
                request,
                "User account and linked employee "
                "details updated successfully."
            )

            return redirect(
                'user_account_list'
            )

        for field, errors in serializer.errors.items():
            for error in errors:
                messages.error(
                    request,
                    f"{field}: {error}"
                )

    return render(
        request,
        'accounts/user_account_edit.html',
        {
            'account': account,
            'roles': roles
        }
    )
