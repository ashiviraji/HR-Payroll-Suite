
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountInvitationTokenGenerator(PasswordResetTokenGenerator):

    def _make_hash_value(self, user, timestamp):
        return (
            f"{user.pk}"
            f"{user.password}"
            f"{user.is_active}"
            f"{user.email}"
            f"{timestamp}"
        )

    def check_token(self, user, token):
        # Use the project's 24-hour invitation expiry
        self.timeout = getattr(
            settings,
            'ACCOUNT_INVITATION_TIMEOUT',
            86400
        )
        return super().check_token(user, token)


account_invitation_token = AccountInvitationTokenGenerator()
