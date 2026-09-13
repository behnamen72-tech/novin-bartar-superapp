# Central import point for SQLAlchemy metadata, Alembic, and ORM event registration.
# Import order is intentional.

from app.core.organization.models import Organization
from app.core.people.models import Person, PersonOrganizationRelationship
from app.core.identity.models import User, UserSession
from app.core.access.models import Permission, Role, RolePermission, UserRoleAssignment
from app.core.audit.models import AuditEvent
from app.core.notifications.models import Notification
from app.core.workflow.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowState,
    WorkflowTransition,
    WorkflowTransitionRecord,
)
from app.modules.hr.models import HREmployment, HRJobProfile, HRPosition
from app.modules.customers.models import CustomerCRMRecord, CustomerCRMTag, CustomerNote, CustomerTag
from app.modules.suppliers.models import (
    SupplierExternalReference,
    SupplierNote,
    SupplierProfile,
    SupplierProfileTag,
    SupplierRepresentative,
    SupplierTag,
)
from app.core.documents.models import (
    Document,
    DocumentCategory,
    DocumentLink,
    DocumentPermission,
    DocumentVersion,
    RetentionPolicy,
    StorageObject,
)

# Registers persist-time business invariants and audit immutability.
import app.core.organization.events  # noqa: F401, E402
import app.core.audit.events  # noqa: F401, E402
import app.core.workflow.events  # noqa: F401, E402
import app.core.notifications.events  # noqa: F401, E402

__all__ = [
    "Organization",
    "Person",
    "PersonOrganizationRelationship",
    "User",
    "UserSession",
    "Permission",
    "Role",
    "RolePermission",
    "UserRoleAssignment",
    "AuditEvent",
    "Notification",
    "WorkflowDefinition",
    "WorkflowState",
    "WorkflowTransition",
    "WorkflowInstance",
    "WorkflowTransitionRecord",
    "Document",
    "DocumentCategory",
    "RetentionPolicy",
    "DocumentVersion",
    "StorageObject",
    "DocumentLink",
    "DocumentPermission",
    "HRJobProfile",
    "HRPosition",
    "HREmployment",
    "CustomerCRMRecord",
    "CustomerCRMTag",
    "CustomerNote",
    "CustomerTag",
    "SupplierProfile",
    "SupplierRepresentative",
    "SupplierNote",
    "SupplierTag",
    "SupplierProfileTag",
    "SupplierExternalReference",
]
