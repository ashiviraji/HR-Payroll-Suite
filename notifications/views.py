
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404,
)
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Notification


# =========================================================
# 1. VIEW NOTIFICATIONS
# =========================================================

@login_required
def notification_list(request):
    """
    Display notifications belonging to
    the currently logged-in user.
    """

    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')

    unread_count = notifications.filter(
        is_read=False
    ).count()

    return render(
        request,
        'notifications/notification_list.html',
        {
            'notifications': notifications,
            'unread_count': unread_count,
        }
    )


# =========================================================
# 2. MARK NOTIFICATION AS READ
# =========================================================

@login_required
@require_POST
def notification_mark_read(request, notification_id):
    """
    Mark a notification as read.
    """

    notification = get_object_or_404(
        Notification,
        notification_id=notification_id,
        recipient=request.user
    )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()

        notification.save(
            update_fields=['is_read', 'read_at']
        )

    messages.success(
        request,
        'Notification marked as read.'
    )

    return redirect('notification_list')


# =========================================================
# 3. DELETE NOTIFICATION
# =========================================================

@login_required
@require_POST
def notification_delete(request, notification_id):
    """
    Delete a notification belonging
    to the currently logged-in user.
    """

    notification = get_object_or_404(
        Notification,
        notification_id=notification_id,
        recipient=request.user
    )

    notification.delete()

    messages.success(
        request,
        'Notification deleted successfully.'
    )

    return redirect('notification_list')


# =========================================================
# 4. MARK ALL NOTIFICATIONS AS READ
# =========================================================

@login_required
@require_POST
def notification_mark_all_read(request):
    """
    Mark all unread notifications as read
    for the currently logged-in user.
    """

    Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(
        is_read=True,
        read_at=timezone.now()
    )

    messages.success(
        request,
        'All notifications marked as read.'
    )

    return redirect('notification_list')
