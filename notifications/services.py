
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from .models import Notification


logger = logging.getLogger(__name__)


# =========================================================
# GENERAL EMAIL NOTIFICATION SERVICE
# =========================================================

def send_notification_email(subject, message, recipient_email):
    """
    Send an email using Django's configured Gmail SMTP service.

    Returns True if the SMTP server accepts the message.
    Returns False if the email cannot be sent.
    """

    if not recipient_email or not recipient_email.strip():
        logger.warning(
            "Email notification skipped: recipient email is missing."
        )
        return False

    try:
        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email.strip()],
            fail_silently=False
        )

        if result == 1:
            logger.info("Email notification sent successfully.")
            return True

        return False

    except Exception:
        logger.exception("Failed to send email notification.")
        return False


# =========================================================
# LEAVE REQUEST SUBMISSION EMAIL
# =========================================================

def send_leave_request_notification(
    manager_email,
    employee_name,
    leave_type,
    start_date,
    end_date
):
    """
    Notify the line manager when an employee
    submits a new leave request.
    """

    subject = "HR Payroll System - New Leave Request"

    message = (
        "Hello,\n\n"
        f"{employee_name} has submitted a new leave request.\n\n"
        f"Leave Type: {leave_type}\n"
        f"Start Date: {start_date}\n"
        f"End Date: {end_date}\n\n"
        "Please log in to the HR Payroll System "
        "to review the request.\n\n"
        "Regards,\n"
        "HR Payroll System"
    )

    return send_notification_email(
        subject,
        message,
        manager_email
    )


# =========================================================
# LEAVE APPROVAL / REJECTION EMAIL
# =========================================================

def send_leave_status_notification(
    employee_email,
    employee_name,
    leave_type,
    status
):
    """
    Notify an employee when their leave request
    is approved or rejected.
    """

    subject = f"HR Payroll System - Leave {status}"

    message = (
        f"Hello {employee_name},\n\n"
        "Your leave request status has been updated.\n\n"
        f"Leave Type: {leave_type}\n"
        f"Status: {status}\n\n"
        "Please log in to the HR Payroll System "
        "for more details.\n\n"
        "Regards,\n"
        "HR Payroll System"
    )

    return send_notification_email(
        subject,
        message,
        employee_email
    )


# =========================================================
# CREATE PAYROLL PENDING NOTIFICATIONS
# =========================================================

def create_pending_payroll_notifications(payroll_run):
    """
    Create notifications for Payroll Admin users
    when a payroll run is pending.

    Prevent duplicate unread notifications
    for the same payroll run and recipient.
    """

    User = get_user_model()

    # -----------------------------------------------------
    # FIND PAYROLL ADMIN USERS
    # -----------------------------------------------------

    payroll_admins = User.objects.filter(
        is_active=True,
        role__role_name='PAYROLL_ADMIN'
    )

    created_count = 0

    # -----------------------------------------------------
    # CREATE NOTIFICATIONS
    # -----------------------------------------------------

    for admin_user in payroll_admins:

        # Check for an existing unread notification
        existing_notification = Notification.objects.filter(
            recipient=admin_user,
            notification_type='PAYROLL',
            related_entity='PayrollRun',
            related_entity_id=payroll_run.run_id,
            is_read=False
        ).exists()

        if existing_notification:
            continue

        Notification.objects.create(
            recipient=admin_user,
            notification_type='PAYROLL',
            title='Pending Payroll Requires Attention',
            message=(
                f'Payroll Run #{payroll_run.run_id} '
                f'for period {payroll_run.period} '
                f'is pending and requires review.'
            ),
            related_entity='PayrollRun',
            related_entity_id=payroll_run.run_id
        )

        created_count += 1

    logger.info(
        "Created %s payroll notification(s) "
        "for payroll run #%s.",
        created_count,
        payroll_run.run_id
    )

    return created_count
