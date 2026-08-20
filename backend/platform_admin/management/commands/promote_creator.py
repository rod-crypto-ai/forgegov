from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.models import PasskeyCredential, TOTPDevice
from platform_admin.models import PlatformAdminGrant


class Command(BaseCommand):
    help = "Promote an existing MFA-enabled ForgeGov user to Creator / Platform Owner."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)

    def handle(self, *args, **options):
        User = get_user_model()
        email = str(options["email"]).strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            raise CommandError("Create and verify the ForgeGov account first, then run this command.")
        has_totp = TOTPDevice.objects.filter(user=user, active=True, confirmed_at__isnull=False).exists()
        has_passkey = PasskeyCredential.objects.filter(user=user, active=True).exists()
        if not (has_totp or has_passkey):
            raise CommandError("Creator access requires MFA. Enable an authenticator or passkey first.")
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save(update_fields=["is_staff", "is_superuser", "is_active"])
        grant, _ = PlatformAdminGrant.objects.update_or_create(
            user=user,
            defaults={"role": PlatformAdminGrant.Role.CREATOR, "is_active": True, "mfa_verified": True},
        )
        self.stdout.write(self.style.SUCCESS(f"Creator access enabled for {user.email}. Grant {grant.id}."))
