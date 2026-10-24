
from django.urls import path
from .web_views import audit_log_list

urlpatterns = [
    path(
        '',
        audit_log_list,
        name='audit_log_list'
    ),
]
