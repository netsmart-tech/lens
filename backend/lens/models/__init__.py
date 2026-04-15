"""Re-exports so Alembic's autogenerate can discover all mapped classes."""

from lens.db.base import CoreBase, TenantBase  # noqa: F401

# Core tables
from lens.models.core.tenants import Tenant  # noqa: F401
from lens.models.core.users import User  # noqa: F401
from lens.models.core.user_tenants import UserTenant  # noqa: F401
from lens.models.core.activities import Activity  # noqa: F401
from lens.models.core.sync_state import SyncState  # noqa: F401
from lens.models.core.reports import Report  # noqa: F401
from lens.models.core.audit_log import AuditLog  # noqa: F401

# Tenant tables
from lens.models.tenant.jira_sites import JiraSite  # noqa: F401
from lens.models.tenant.jira_issues import JiraIssue  # noqa: F401
from lens.models.tenant.jira_comments import JiraComment  # noqa: F401
from lens.models.tenant.jira_changelog import JiraChangelog  # noqa: F401
from lens.models.tenant.jira_worklogs import JiraWorklog  # noqa: F401
from lens.models.tenant.jira_issue_links import JiraIssueLink  # noqa: F401
