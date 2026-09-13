export type CurrentUser = {
  id: string;
  person_id: string;
  email: string;
  username: string | null;
  is_active: boolean;
};

export type ScopeMode = "self" | "self_and_descendants";

export type AccessAssignment = {
  role_code: string;
  organization_id: string;
  organization_name: string;
  scope_mode: ScopeMode;
  permissions: string[];
};

export type SessionSnapshot = {
  user: CurrentUser;
  assignments: AccessAssignment[];
};

export type OrganizationType = "holding" | "company" | "branch" | "unit";

export type OrganizationItem = {
  id: string;
  name: string;
  code: string;
  organization_type: OrganizationType;
  parent_id: string | null;
  is_active: boolean;
};

export type PersonRelationshipItem = {
  id: string;
  organization_id: string;
  organization_name: string;
  relationship_code: string;
  start_date: string | null;
  end_date: string | null;
  is_active: boolean;
};

export type PersonItem = {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  relationships: PersonRelationshipItem[];
};

export type UserItem = {
  id: string;
  person_id: string;
  person_name: string;
  email: string;
  username: string | null;
  is_active: boolean;
  last_login_at: string | null;
  organization_names: string[];
};

export type AccessOverviewItem = {
  id: string;
  user_id: string;
  user_email: string;
  user_name: string;
  role_code: string;
  role_name: string;
  organization_id: string;
  organization_name: string;
  scope_mode: ScopeMode;
  is_active: boolean;
  permissions: string[];
};

export type AuditEventItem = {
  id: string;
  actor_user_id: string | null;
  actor_identifier: string | null;
  organization_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  event_metadata: Record<string, unknown> | null;
  source: string;
  request_id: string | null;
  occurred_at: string;
};

export type DocumentStatus = "active" | "archived" | "disabled";
export type DocumentPriority = "low" | "normal" | "high" | "critical";

export type DocumentItem = {
  id: string;
  title: string;
  document_type: string;
  description: string | null;
  priority: DocumentPriority;
  status: DocumentStatus;
  organization_id: string;
  created_by: string;
  category_id: string | null;
  expires_at: string | null;
  retention_policy_id: string | null;
  retention_review_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentExpirationState = "active" | "expired" | "expiring_soon";

export type DocumentExpirationItem = {
  document: DocumentItem;
  expiration_state: DocumentExpirationState;
  days_remaining: number;
};

export type DocumentVersionItem = {
  id: string;
  document_id: string;
  version_number: number;
  file_name: string;
  mime_type: string;
  created_by: string;
  created_at: string;
  size_bytes: number;
  checksum: string | null;
};

export type DocumentLinkEntityType = "organization" | "person";

export type DocumentLinkItem = {
  id: string;
  document_id: string;
  entity_type: DocumentLinkEntityType;
  entity_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type DocumentDetailItem = DocumentItem & {
  versions: DocumentVersionItem[];
  links: DocumentLinkItem[];
};

export type DocumentCategoryItem = {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  description: string | null;
  parent_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type RetentionBasis = "created_at" | "expires_at";

export type RetentionPolicyItem = {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  description: string | null;
  retention_days: number;
  basis: RetentionBasis;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type DocumentTimelineEventItem = {
  id: string;
  action: string;
  actor_identifier: string | null;
  occurred_at: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  event_metadata: Record<string, unknown> | null;
};

export type PermissionCatalogItem = {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
};

export type RoleAdminItem = {
  id: string;
  code: string;
  name: string;
  description: string | null;
  organization_id: string | null;
  organization_name: string | null;
  is_system: boolean;
  is_active: boolean;
  permissions: string[];
};

export type AccessAssignmentAdminItem = {
  id: string;
  user_id: string;
  role_id: string;
  role_code: string;
  organization_id: string;
  organization_name: string;
  scope_mode: ScopeMode;
  starts_at: string | null;
  ends_at: string | null;
  is_active: boolean;
};

export type DocumentPermissionType = "read" | "manage";

export type DocumentPermissionItem = {
  id: string;
  document_id: string;
  role_id: string;
  permission_type: DocumentPermissionType;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};


export type WorkflowDefinitionStatus = "draft" | "published" | "retired";
export type WorkflowInstanceStatus = "active" | "completed" | "cancelled";

export type WorkflowOrganizationCapability = {
  id: string;
  name: string;
  code: string;
  organization_type: OrganizationType;
  parent_id: string | null;
  is_active: boolean;
  can_read: boolean;
  can_manage: boolean;
  can_execute: boolean;
};

export type WorkflowStateItem = {
  id: string;
  code: string;
  name: string;
  position: number;
  is_initial: boolean;
  is_terminal: boolean;
};

export type WorkflowTransitionItem = {
  id: string;
  code: string;
  name: string;
  from_state_id: string;
  to_state_id: string;
};

export type WorkflowDefinitionItem = {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  description: string | null;
  version: number;
  scope_mode: ScopeMode;
  status: WorkflowDefinitionStatus;
  states: WorkflowStateItem[];
  transitions: WorkflowTransitionItem[];
};

export type WorkflowTransitionRecordItem = {
  id: string;
  transition_id: string;
  from_state_id: string;
  to_state_id: string;
  actor_user_id: string;
  comment: string | null;
  occurred_at: string;
};

export type WorkflowInstanceItem = {
  id: string;
  definition_id: string;
  organization_id: string;
  resource_type: string;
  resource_id: string;
  current_state_id: string;
  status: WorkflowInstanceStatus;
  started_by_user_id: string;
  completed_at: string | null;
  cancelled_at: string | null;
  history: WorkflowTransitionRecordItem[];
};

export type NotificationSeverity = "info" | "success" | "warning" | "critical";

export type NotificationItem = {
  id: string;
  recipient_user_id: string;
  organization_id: string | null;
  event_code: string;
  source: string;
  severity: NotificationSeverity;
  title: string;
  body: string | null;
  resource_type: string | null;
  resource_id: string | null;
  action_path: string | null;
  created_at: string;
  read_at: string | null;
};

export type NotificationUnreadCount = {
  unread_count: number;
};

export type NotificationReadAllResult = {
  marked_read: number;
};

export type SearchEntityType = "organization" | "person" | "document" | "customer" | "supplier";

export type SearchResultItem = {
  entity_type: SearchEntityType;
  id: string;
  title: string;
  subtitle: string | null;
  organization_id: string | null;
  organization_name: string | null;
  action_path: string;
};

export type SearchResponse = {
  query: string;
  results: SearchResultItem[];
  counts: Record<string, number>;
};

export type HROrganizationCapability = {
  id: string;
  name: string;
  code: string;
  organization_type: OrganizationType;
  parent_id: string | null;
  is_active: boolean;
  can_read: boolean;
  can_manage: boolean;
};

export type HRJobProfileItem = {
  id: string;
  organization_id: string;
  code: string;
  title: string;
  description: string | null;
  scope_mode: ScopeMode;
  is_active: boolean;
};

export type HRJobProfileSummary = {
  id: string;
  code: string;
  title: string;
  organization_id: string;
  is_active: boolean;
};

export type HRPositionItem = {
  id: string;
  organization_id: string;
  job_profile_id: string;
  code: string;
  name: string | null;
  reports_to_position_id: string | null;
  is_active: boolean;
  job_profile: HRJobProfileSummary;
};

export type HREmploymentType =
  | "permanent"
  | "fixed_term"
  | "part_time"
  | "contractor"
  | "intern"
  | "other";

export type HRPersonOption = {
  id: string;
  first_name: string;
  last_name: string;
};

export type HREmploymentItem = {
  id: string;
  organization_id: string;
  person_id: string;
  position_id: string | null;
  employment_number: string | null;
  employment_type: HREmploymentType;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
  person: {
    id: string;
    first_name: string;
    last_name: string;
    is_active: boolean;
  };
  position: {
    id: string;
    code: string;
    name: string | null;
    is_active: boolean;
  } | null;
};


export type CustomerCRMType =
  | "individual"
  | "household"
  | "business"
  | "retail"
  | "wholesale"
  | "other";

export type CustomerCommercialStatus =
  | "prospect"
  | "active"
  | "inactive"
  | "blocked"
  | "archived";

export type CustomerCRMSource =
  | "manual"
  | "commerce_activity"
  | "phone_order"
  | "import"
  | "other";

export type CRMOrganizationCapability = {
  id: string;
  name: string;
  code: string;
  organization_type: OrganizationType;
  parent_id: string | null;
  is_active: boolean;
  can_read: boolean;
  can_manage: boolean;
  can_read_notes: boolean;
  can_manage_notes: boolean;
  can_assign: boolean;
  can_manage_tags: boolean;
  can_read_commerce_activity: boolean;
};

export type CRMAssigneeOption = {
  id: string;
  email: string;
  display_name: string;
};

export type CustomerTagItem = {
  id: string;
  organization_id: string;
  name: string;
  is_active: boolean;
};

export type CustomerCRMItem = {
  id: string;
  organization_id: string;
  commerce_customer_ref: string;
  customer_type: CustomerCRMType;
  commercial_status: CustomerCommercialStatus;
  source: CustomerCRMSource;
  display_label: string;
  assigned_owner_user_id: string | null;
  created_by_user_id: string;
  is_active: boolean;
  version: number;
  tags: CustomerTagItem[];
};

export type CustomerNoteItem = {
  id: string;
  customer_crm_record_id: string;
  author_user_id: string;
  body: string;
  version: number;
  created_at: string;
  updated_at: string;
};

export type CommerceActivityItem = {
  external_order_ref: string;
  status: string;
  occurred_at: string;
  total_amount_minor: number | null;
  currency: string | null;
};

export type CommerceActivityProjection = {
  source_updated_at: string | null;
  orders: CommerceActivityItem[];
};


export type SupplierKind = "company" | "individual" | "other";
export type SupplierCommercialStatus = "prospect" | "active" | "inactive" | "suspended" | "archived";
export type SupplierSource = "manual" | "import" | "accounting_reference" | "procurement_reference" | "other";
export type SupplierExternalSystem = "accounting" | "erp" | "procurement" | "other";

export type SupplierOrganizationCapability = {
  id: string;
  name: string;
  code: string;
  organization_type: OrganizationType;
  parent_id: string | null;
  is_active: boolean;
  can_read: boolean;
  can_manage: boolean;
  can_read_representatives: boolean;
  can_manage_representatives: boolean;
  can_read_representative_contacts: boolean;
  can_read_notes: boolean;
  can_manage_notes: boolean;
  can_assign: boolean;
  can_manage_tag_catalog: boolean;
  can_assign_tags: boolean;
  can_read_external_references: boolean;
  can_manage_external_references: boolean;
};

export type SupplierAssigneeOption = { id: string; email: string; display_name: string };

export type SupplierTagItem = {
  id: string;
  organization_id: string;
  name: string;
  is_active: boolean;
};

export type SupplierItem = {
  id: string;
  organization_id: string;
  supplier_kind: SupplierKind;
  display_name: string;
  commercial_status: SupplierCommercialStatus;
  source: SupplierSource;
  assigned_owner_user_id: string | null;
  created_by_user_id: string;
  is_active: boolean;
  version: number;
  tags: SupplierTagItem[];
};

export type SupplierRepresentativeItem = {
  id: string;
  supplier_id: string;
  display_name: string;
  job_title: string | null;
  phone: string | null;
  email: string | null;
  contact_masked: boolean;
  is_primary: boolean;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
};

export type SupplierNoteItem = {
  id: string;
  supplier_id: string;
  author_user_id: string;
  body: string;
  version: number;
  created_at: string;
  updated_at: string;
};

export type SupplierExternalReferenceItem = {
  id: string;
  supplier_id: string;
  organization_id: string;
  system: SupplierExternalSystem;
  external_id: string;
  created_by_user_id: string;
  created_at: string;
};
