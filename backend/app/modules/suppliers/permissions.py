SUPPLIER_READ = "supplier.read"
SUPPLIER_MANAGE = "supplier.manage"
SUPPLIER_REPRESENTATIVE_READ = "supplier.representative.read"
SUPPLIER_REPRESENTATIVE_MANAGE = "supplier.representative.manage"
SUPPLIER_REPRESENTATIVE_CONTACT_READ = "supplier.representative.contact.read"
SUPPLIER_NOTES_READ = "supplier.notes.read"
SUPPLIER_NOTES_MANAGE = "supplier.notes.manage"
SUPPLIER_ASSIGN = "supplier.assign"
SUPPLIER_TAGS_CATALOG_MANAGE = "supplier.tags.catalog.manage"
SUPPLIER_TAGS_ASSIGN = "supplier.tags.assign"
SUPPLIER_EXTERNAL_REFERENCE_READ = "supplier.external_reference.read"
SUPPLIER_EXTERNAL_REFERENCE_MANAGE = "supplier.external_reference.manage"

SUPPLIER_PERMISSION_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    (SUPPLIER_READ, "Read suppliers", "View organization-scoped supplier operational metadata."),
    (SUPPLIER_MANAGE, "Manage suppliers", "Create and update organization-scoped supplier operational metadata."),
    (SUPPLIER_REPRESENTATIVE_READ, "Read supplier representatives", "View supplier representatives in authorized supplier scope."),
    (SUPPLIER_REPRESENTATIVE_MANAGE, "Manage supplier representatives", "Create and update supplier representatives in authorized supplier scope."),
    (SUPPLIER_REPRESENTATIVE_CONTACT_READ, "Read supplier representative contacts", "View unmasked representative phone and email values."),
    (SUPPLIER_NOTES_READ, "Read supplier notes", "View supplier notes within authorized organization scope."),
    (SUPPLIER_NOTES_MANAGE, "Manage supplier notes", "Create and edit supplier notes within authorized organization scope."),
    (SUPPLIER_ASSIGN, "Assign supplier owners", "Assign or unassign internal owners for supplier records."),
    (SUPPLIER_TAGS_CATALOG_MANAGE, "Manage supplier tag catalog", "Create organization-owned supplier tag vocabulary."),
    (SUPPLIER_TAGS_ASSIGN, "Assign supplier tags", "Attach or remove existing organization-owned tags on suppliers."),
    (SUPPLIER_EXTERNAL_REFERENCE_READ, "Read supplier external references", "View supplier external-system reference metadata."),
    (SUPPLIER_EXTERNAL_REFERENCE_MANAGE, "Manage supplier external references", "Create and remove supplier external-system references."),
)
