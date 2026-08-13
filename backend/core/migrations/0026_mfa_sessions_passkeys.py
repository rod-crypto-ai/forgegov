from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0025_identity_account_foundation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationSecurityPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("require_mfa", models.BooleanField(default=False)),
                ("require_mfa_for_financial_roles", models.BooleanField(default=False)),
                ("session_max_days", models.PositiveSmallIntegerField(default=7)),
                ("organization", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="security_policy", to="core.organization")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_org_security_policies", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="TOTPDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(default="Authenticator app", max_length=120)),
                ("secret_encrypted", models.TextField()),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("active", models.BooleanField(default=False)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="totp_device", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="RecoveryCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code_hash", models.CharField(max_length=64)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recovery_codes", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddConstraint(
            model_name="recoverycode",
            constraint=models.UniqueConstraint(fields=("user", "code_hash"), name="uniq_recovery_user_hash"),
        ),
        migrations.AddIndex(
            model_name="recoverycode",
            index=models.Index(fields=["user", "used_at"], name="recovery_user_used_idx"),
        ),
        migrations.CreateModel(
            name="PasskeyCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(default="Passkey", max_length=120)),
                ("credential_id", models.TextField(unique=True)),
                ("public_key", models.TextField()),
                ("sign_count", models.PositiveBigIntegerField(default=0)),
                ("transports", models.JSONField(blank=True, default=list)),
                ("device_type", models.CharField(blank=True, max_length=40)),
                ("backed_up", models.BooleanField(default=False)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="passkey_credentials", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="passkeycredential",
            index=models.Index(fields=["user", "active"], name="passkey_user_active_idx"),
        ),
        migrations.CreateModel(
            name="AuthSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("session_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("refresh_jti", models.CharField(blank=True, max_length=255)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("device_label", models.CharField(blank=True, max_length=255)),
                ("expires_at", models.DateTimeField()),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("step_up_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="auth_sessions", to="core.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="forgegov_auth_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-last_seen_at", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="authsession",
            index=models.Index(fields=["user", "revoked_at", "-last_seen_at"], name="authsess_user_rev_idx"),
        ),
        migrations.AddIndex(
            model_name="authsession",
            index=models.Index(fields=["session_id"], name="authsess_sid_idx"),
        ),
        migrations.CreateModel(
            name="SecurityChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("purpose", models.CharField(choices=[("mfa_login", "MFA Login"), ("mfa_enrollment", "MFA Enrollment"), ("webauthn_register", "WebAuthn Registration"), ("webauthn_auth", "WebAuthn Authentication")], max_length=30)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("challenge", models.TextField(blank=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="security_challenges", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="securitychallenge",
            index=models.Index(fields=["user", "purpose", "expires_at"], name="secchal_user_purp_idx"),
        ),
    ]
