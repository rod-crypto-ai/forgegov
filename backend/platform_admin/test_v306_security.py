from django.contrib.auth import get_user_model
from django.test import TestCase

from .security import restore_user_access, revoke_user_access

User = get_user_model()


class PlatformAdminV306SecurityTests(TestCase):
    def make_user(self, value):
        kwargs = {User.USERNAME_FIELD: value}
        if User.USERNAME_FIELD != "email":
            kwargs["email"] = f"{value}@example.com"
        return User.objects.create_user(password="temporary-test-password", **kwargs)

    def test_revoke_user_access_disables_account(self):
        user = self.make_user("v306-suspend")
        result = revoke_user_access(user)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(result["user_disabled"])

    def test_restore_user_access_requires_new_login(self):
        user = self.make_user("v306-reactivate")
        revoke_user_access(user)
        self.assertTrue(restore_user_access(user))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
