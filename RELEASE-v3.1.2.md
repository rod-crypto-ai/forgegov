# ForgeGov v3.1.2 — Alerts, Notifications & Daily Intelligence

## Highlights
- Unified notification center combines intelligence alerts, collaboration activity, invitations, and delivery history.
- Per-user, per-workspace delivery preferences for in-app alerts, email, opportunity matches/changes, deadlines, pipeline, Project Rooms, security, and daily/weekly briefs.
- Saved-search evaluations run hourly and fan out matching opportunities into the in-app notification experience.
- Opportunity source-version monitoring detects deadline changes, set-aside changes, cancellation/inactive status, new attachments, and general amendments without duplicate events.
- Deadline monitoring covers opportunity response dates, pipeline follow-ups, and assigned ForgeGov tasks.
- Project Room task/comment/file notifications respect owner/partner visibility boundaries; pricing and sensitive file existence is not broadcast.
- Daily and weekly intelligence email briefs summarize new intelligence, upcoming deadlines, and workspace activity.
- Tracked email delivery records expose sent, failed, and skipped deliveries.
- Creator / Platform Owner can globally pause/resume notification delivery, send a controlled test to their own account, and inspect recent delivery failures.
- Render worker configuration receives SMTP settings so Celery-based alerts and digests can send production email.

## Data changes
- Migration `core.0030_notifications_daily_intelligence` adds durable alert event keys, notification preferences, and notification delivery history.

## Release discipline
- This release must pass `VERIFY_V3.1.2.command` completely, including health/readiness, before commit, push, or tagging.

## Release hygiene
- Removes the obsolete root `INSTALL.command` / `VERIFY.command` v1.0-era scripts so operators use the versioned v3.1.2 verifier instead of stale release tooling.

## Upgrade baseline
- The package preserves the validated v3.1.1 `frontend/package-lock.json` during overlay installation so the post-release dependency-security fixes are not regressed. See `UPGRADE-v3.1.2.md`.
