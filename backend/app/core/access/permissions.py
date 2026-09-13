# Canonical Core permission codes. Business modules will add their own codes later.
ORGANIZATION_READ = "organization.read"
ORGANIZATION_MANAGE = "organization.manage"
PEOPLE_READ = "people.read"
PEOPLE_MANAGE = "people.manage"
USERS_READ = "users.read"
USERS_MANAGE = "users.manage"
ACCESS_READ = "access.read"
ACCESS_MANAGE = "access.manage"
AUDIT_READ = "audit.read"
DOCUMENTS_READ = "documents.read"
DOCUMENTS_MANAGE = "documents.manage"
WORKFLOW_READ = "workflow.read"
WORKFLOW_MANAGE = "workflow.manage"
WORKFLOW_EXECUTE = "workflow.execute"

CORE_PERMISSION_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    (ORGANIZATION_READ, "Read organizations", "View organization structures."),
    (ORGANIZATION_MANAGE, "Manage organizations", "Create and change organization structures."),
    (PEOPLE_READ, "Read people", "View people records within authorized organization scope."),
    (PEOPLE_MANAGE, "Manage people", "Create and change people records within authorized scope."),
    (USERS_READ, "Read users", "View system-user identities within authorized scope."),
    (USERS_MANAGE, "Manage users", "Create, activate, deactivate, or update system users."),
    (ACCESS_READ, "Read access", "View roles, permissions, and access assignments."),
    (ACCESS_MANAGE, "Manage access", "Manage roles, permissions, and access assignments."),
    (
        AUDIT_READ,
        "Read audit history",
        "View immutable audit events within authorized organization scope.",
    ),
    (DOCUMENTS_READ, "Read documents", "View documents within authorized organization scope."),
    (
        DOCUMENTS_MANAGE,
        "Manage documents",
        "Create and manage documents within authorized organization scope.",
    ),
    (
        WORKFLOW_READ,
        "Read workflows",
        "View workflow definitions and instances within authorized organization scope.",
    ),
    (
        WORKFLOW_MANAGE,
        "Manage workflows",
        "Create, version, publish, and retire workflow definitions within authorized scope.",
    ),
    (
        WORKFLOW_EXECUTE,
        "Execute workflows",
        "Start and advance workflow instances within authorized organization scope.",
    ),
)
