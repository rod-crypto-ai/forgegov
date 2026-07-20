# Architecture

## System boundaries

- **Next.js:** browser application, responsive navigation, dashboards, search, pipeline, collaboration views.
- **Django REST Framework:** authentication, permissions, relational business logic, API, admin console.
- **PostgreSQL:** source of truth for users, workspaces, normalized opportunities, pursuits, tasks, contacts, and audit records.
- **Redis:** caching, Celery broker, task coordination, and short-lived state.
- **Celery:** government-data ingestion, alert delivery, document parsing, and AI jobs.
- **Object storage:** solicitation attachments and workspace files in a later milestone.
- **OpenSearch:** high-volume full-text and faceted search in a later milestone.

## Tenant model

Every business record belongs to an organization. Membership records define user roles. API querysets must always be scoped to organizations the authenticated user belongs to. This rule is non-negotiable because weak tenant isolation would expose private capture data.

## Data-source strategy

The application separates external source records from user-managed capture records. Government data can refresh without overwriting internal notes, tasks, scoring, or pipeline decisions.

## Initial API routes

- `GET /api/health/`
- `GET /api/integrations/status/`
- `GET /api/opportunities/`
- `POST /api/opportunities/`
- `GET /api/pipeline/`
- `POST /api/pipeline/`
- `GET /api/tasks/`
- `POST /api/tasks/`
- `GET /api/saved-searches/`
- `POST /api/saved-searches/`
- `GET /api/live/sam/opportunities/`
- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`
