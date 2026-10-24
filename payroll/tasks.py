
import logging

from celery import shared_task
from django.utils import timezone

from notifications.services import (
    create_pending_payroll_notifications,
)

from .models import PayrollRun
from .services import process_payroll_service


logger = logging.getLogger(__name__)


# =========================================================
# 1. TEST CELERY BACKGROUND TASK
# =========================================================

@shared_task
def test_payroll_task():
    """
    Verify that Celery background processing works.

    This task tests the connection between
    Django, Redis, and the Celery Worker.
    """

    message = (
        "Celery background task executed "
        "successfully for HR Payroll System!"
    )

    logger.info(message)

    return message


# =========================================================
# 2. BACKGROUND PAYROLL PROCESSING
# =========================================================

@shared_task(bind=True, max_retries=0)
def process_payroll_task(
    self,
    run_id,
    initiated_by_user_id
):
    """
    Process payroll asynchronously.

    Workflow:
    1. Receive the payroll run ID.
    2. Execute the payroll processing service.
    3. Calculate employee salaries and taxes.
    4. Create employee payslip records.
    5. Update payroll status to COMPLETED.
    6. Mark the run as FAILED if processing fails.

    The payroll run must already have
    PROCESSING status.
    """

    # -----------------------------------------------------
    # LOG PAYROLL PROCESSING START
    # -----------------------------------------------------

    logger.info(
        "Starting payroll processing for run #%s",
        run_id
    )

    try:

        # -------------------------------------------------
        # EXECUTE EXISTING PAYROLL SERVICE
        # -------------------------------------------------

        result = process_payroll_service(
            run_id=run_id,
            initiated_by_user_id=initiated_by_user_id
        )

        # -------------------------------------------------
        # LOG SUCCESSFUL PROCESSING
        # -------------------------------------------------

        logger.info(
            "Payroll run #%s completed successfully.",
            run_id
        )

        return result

    except Exception:

        # -------------------------------------------------
        # LOG PROCESSING FAILURE
        # -------------------------------------------------

        logger.exception(
            "Payroll processing failed for run #%s",
            run_id
        )

        # -------------------------------------------------
        # UPDATE PAYROLL STATUS TO FAILED
        # -------------------------------------------------

        # Only update payroll runs that are still
        # PROCESSING. Do not overwrite completed runs.

        updated = PayrollRun.objects.filter(
            pk=run_id,
            status='PROCESSING'
        ).update(
            status='FAILED'
        )

        if updated:

            logger.warning(
                "Payroll run #%s marked as FAILED.",
                run_id
            )

        raise


# =========================================================
# 3. SCHEDULED PAYROLL CHECK USING CELERY BEAT
# =========================================================

@shared_task
def check_scheduled_payroll_task():
    """
    Identify due pending payroll runs and create
    notifications for Payroll Admin users.

    This task runs according to the schedule
    configured in Django Admin using Celery Beat.

    Workflow:
    1. Identify the current payroll month.
    2. Retrieve pending payroll runs.
    3. Exclude future payroll periods.
    4. Count due payroll runs.
    5. Create notifications for Payroll Admins.
    6. Avoid duplicate unread notifications.
    7. Log the results.
    8. Return a summary.

    IMPORTANT:
    This task does not process payroll,
    calculate salaries, or generate payslips.
    """

    # -----------------------------------------------------
    # GET CURRENT MONTH
    # -----------------------------------------------------

    current_month = timezone.localdate().strftime(
        '%Y-%m'
    )

    logger.info(
        "Starting scheduled payroll check "
        "for current month: %s",
        current_month
    )

    # -----------------------------------------------------
    # RETRIEVE DUE PENDING PAYROLL RUNS
    # -----------------------------------------------------

    # Payroll periods use YYYY-MM format.
    #
    # Examples:
    # 2026-05 <= 2026-10 -> Included
    # 2026-10 <= 2026-10 -> Included
    # 2026-12 <= 2026-10 -> Excluded

    due_runs = list(
        PayrollRun.objects.filter(
            status='PENDING',
            period__lte=current_month
        ).order_by(
            'period',
            'run_id'
        )
    )

    # -----------------------------------------------------
    # GET DUE PAYROLL RUN IDS
    # -----------------------------------------------------

    due_run_ids = [
        run.run_id
        for run in due_runs
    ]

    # -----------------------------------------------------
    # COUNT DUE PAYROLL RUNS
    # -----------------------------------------------------

    due_count = len(due_run_ids)

    # -----------------------------------------------------
    # CREATE NOTIFICATIONS FOR PAYROLL ADMINS
    # -----------------------------------------------------

    notifications_created = 0

    for payroll_run in due_runs:

        created_count = (
            create_pending_payroll_notifications(
                payroll_run
            )
        )

        notifications_created += created_count

    # -----------------------------------------------------
    # LOG SCHEDULED CHECK RESULTS
    # -----------------------------------------------------

    logger.info(
        "Scheduled payroll check completed. "
        "Current month: %s. "
        "Found %s due payroll run(s): %s. "
        "Notifications created: %s.",
        current_month,
        due_count,
        due_run_ids,
        notifications_created
    )

    # -----------------------------------------------------
    # LOG IF NO DUE PAYROLL RUNS EXIST
    # -----------------------------------------------------

    if due_count == 0:

        logger.info(
            "No due pending payroll runs found "
            "for %s or earlier.",
            current_month
        )

    # -----------------------------------------------------
    # RETURN SCHEDULED CHECK SUMMARY
    # -----------------------------------------------------

    return {
        'message': 'Scheduled payroll check completed.',
        'current_month': current_month,
        'due_count': due_count,
        'due_run_ids': due_run_ids,
        'notifications_created': notifications_created,
    }
