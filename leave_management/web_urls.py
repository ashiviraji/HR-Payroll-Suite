from django.urls import path
from . import web_views

urlpatterns = [
    path('', web_views.leave_request_list, name='leave_request_list'),
    path('create/', web_views.leave_request_create, name='leave_request_create'),
    path('<int:pk>/edit/', web_views.leave_request_edit, name='leave_request_edit'),
    path('<int:pk>/delete/', web_views.leave_request_delete, name='leave_request_delete'),
    path('<int:pk>/approve/', web_views.leave_request_approve, name='leave_request_approve'),
    path('<int:pk>/reject/', web_views.leave_request_reject, name='leave_request_reject'),
]
