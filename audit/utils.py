
from .models import AuditLog


def create_audit_log(user, action, entity_name, entity_id=None):
    """
    Create an audit log entry for an important system action.
    """

    return AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        entity_name=entity_name,
        entity_id=entity_id,
    )
