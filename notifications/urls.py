
from django.urls import path

from . import views


# =========================================================
# NOTIFICATION URL CONFIGURATION
# =========================================================

urlpatterns = [

    # 1. View all notifications
    path(
        '',
        views.notification_list,
        name='notification_list'
    ),

    # 2. Mark a notification as read
    path(
        '<int:notification_id>/mark-read/',
        views.notification_mark_read,
        name='notification_mark_read'
    ),

    # 3. Delete a notification
    path(
        '<int:notification_id>/delete/',
        views.notification_delete,
        name='notification_delete'
    ),

    # 4. Mark all notifications as read
    path(
        'mark-all-read/',
        views.notification_mark_all_read,
        name='notification_mark_all_read'
    ),

]
