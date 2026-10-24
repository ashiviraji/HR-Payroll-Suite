
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from .models import AuditLog


@login_required
def audit_log_list(request):
    user = request.user

    is_hr_officer = (
        user.role_id is not None
        and user.role.role_name == 'HR_OFFICER'
    )

    if not (user.is_superuser or is_hr_officer):
        raise PermissionDenied(
            "You do not have permission to view audit logs."
        )

    audit_logs = AuditLog.objects.select_related('user').all()

    search_query = request.GET.get('search', '').strip()
    action_filter = request.GET.get('action', '').strip()

    if search_query:
        audit_logs = audit_logs.filter(
            Q(user__username__icontains=search_query)
            | Q(entity_name__icontains=search_query)
        )

    allowed_actions = ['CREATE', 'UPDATE', 'DELETE', 'APPROVE', 'REJECT']

    if action_filter in allowed_actions:
        audit_logs = audit_logs.filter(action=action_filter)

    audit_logs = audit_logs.order_by('-created_at', '-log_id')

    paginator = Paginator(audit_logs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'audit_logs': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'action_filter': action_filter,
        'action_choices': allowed_actions,
    }

    return render(
        request,
        'audit/audit_log_list.html',
        context
    )
