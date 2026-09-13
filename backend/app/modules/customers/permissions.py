CRM_CUSTOMER_READ = "crm.customer.read"
CRM_CUSTOMER_MANAGE = "crm.customer.manage"
CRM_CUSTOMER_NOTES_READ = "crm.customer.notes.read"
CRM_CUSTOMER_NOTES_MANAGE = "crm.customer.notes.manage"
CRM_CUSTOMER_ASSIGN = "crm.customer.assign"
CRM_CUSTOMER_TAGS_MANAGE = "crm.customer.tags.manage"
CRM_CUSTOMER_COMMERCE_ACTIVITY_READ = "crm.customer.commerce_activity.read"

CRM_PERMISSION_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    (
        CRM_CUSTOMER_READ,
        "Read customer CRM",
        "View organization-scoped customer CRM metadata and references.",
    ),
    (
        CRM_CUSTOMER_MANAGE,
        "Manage customer CRM",
        "Create and change organization-scoped customer CRM metadata.",
    ),
    (
        CRM_CUSTOMER_NOTES_READ,
        "Read customer notes",
        "View customer CRM notes within authorized organization scope.",
    ),
    (
        CRM_CUSTOMER_NOTES_MANAGE,
        "Manage customer notes",
        "Create and edit customer CRM notes within authorized organization scope.",
    ),
    (
        CRM_CUSTOMER_ASSIGN,
        "Assign customer owners",
        "Assign or unassign internal owners for customer CRM records.",
    ),
    (
        CRM_CUSTOMER_TAGS_MANAGE,
        "Manage customer tags",
        "Create and attach organization-owned CRM tags.",
    ),
    (
        CRM_CUSTOMER_COMMERCE_ACTIVITY_READ,
        "Read customer commerce activity",
        "View authorized commerce activity projections for customer CRM records.",
    ),
)
