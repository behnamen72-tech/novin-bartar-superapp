BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20260909_0001

CREATE TYPE organization_type AS ENUM ('HOLDING', 'COMPANY', 'BRANCH', 'UNIT');

CREATE TABLE organizations (
    name VARCHAR(200) NOT NULL, 
    code VARCHAR(50) NOT NULL, 
    organization_type organization_type NOT NULL, 
    parent_id UUID, 
    is_active BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_organizations_parent_not_self CHECK (parent_id IS NULL OR parent_id <> id), 
    FOREIGN KEY(parent_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    UNIQUE (code)
);

CREATE UNIQUE INDEX ix_organizations_code ON organizations (code);

CREATE INDEX ix_organizations_organization_type ON organizations (organization_type);

CREATE INDEX ix_organizations_parent_id ON organizations (parent_id);

CREATE TABLE people (
    first_name VARCHAR(100) NOT NULL, 
    last_name VARCHAR(100) NOT NULL, 
    email VARCHAR(320), 
    phone VARCHAR(50), 
    is_active BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_people_email ON people (email);

CREATE INDEX ix_people_phone ON people (phone);

CREATE TABLE person_organization_relationships (
    person_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    relationship_code VARCHAR(80) NOT NULL, 
    start_date DATE, 
    end_date DATE, 
    is_active BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_person_org_relationship_date_range CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(person_id) REFERENCES people (id) ON DELETE CASCADE
);

CREATE INDEX ix_person_organization_relationships_organization_id ON person_organization_relationships (organization_id);

CREATE INDEX ix_person_organization_relationships_person_id ON person_organization_relationships (person_id);

CREATE INDEX ix_person_organization_relationships_relationship_code ON person_organization_relationships (relationship_code);

CREATE TABLE users (
    person_id UUID NOT NULL, 
    email VARCHAR(320) NOT NULL, 
    username VARCHAR(100), 
    is_active BOOLEAN NOT NULL, 
    last_login_at TIMESTAMP WITH TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(person_id) REFERENCES people (id) ON DELETE RESTRICT, 
    UNIQUE (email), 
    UNIQUE (person_id), 
    UNIQUE (username)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE UNIQUE INDEX ix_users_person_id ON users (person_id);

CREATE UNIQUE INDEX ix_users_username ON users (username);

INSERT INTO alembic_version (version_num) VALUES ('20260909_0001') RETURNING alembic_version.version_num;

-- Running upgrade 20260909_0001 -> 20260909_0002

ALTER TABLE users ADD COLUMN password_hash VARCHAR(512);

UPDATE users SET password_hash = '!legacy-account-disabled!' WHERE password_hash IS NULL;

ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL;

UPDATE alembic_version SET version_num='20260909_0002' WHERE alembic_version.version_num = '20260909_0001';

-- Running upgrade 20260909_0002 -> 20260909_0003

CREATE TABLE permissions (
    code VARCHAR(120) NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    description VARCHAR(500), 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE UNIQUE INDEX ix_permissions_code ON permissions (code);

CREATE TABLE roles (
    code VARCHAR(100) NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    description VARCHAR(500), 
    is_system BOOLEAN DEFAULT false NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE UNIQUE INDEX ix_roles_code ON roles (code);

CREATE TABLE role_permissions (
    role_id UUID NOT NULL, 
    permission_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (role_id, permission_id), 
    FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE, 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
);

CREATE TYPE organization_scope_mode AS ENUM ('SELF', 'SELF_AND_DESCENDANTS');

CREATE TABLE user_role_assignments (
    user_id UUID NOT NULL, 
    role_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    scope_mode organization_scope_mode NOT NULL, 
    starts_at TIMESTAMP WITH TIME ZONE, 
    ends_at TIMESTAMP WITH TIME ZONE, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_user_role_org_scope UNIQUE (user_id, role_id, organization_id, scope_mode)
);

CREATE INDEX ix_user_role_assignments_user_id ON user_role_assignments (user_id);

CREATE INDEX ix_user_role_assignments_role_id ON user_role_assignments (role_id);

CREATE INDEX ix_user_role_assignments_organization_id ON user_role_assignments (organization_id);

INSERT INTO permissions (code, name, description, id) VALUES ('organization.read', 'Read organizations', 'View organization structures.', 'b159bb46-f609-4bc7-aa23-ef85c59490fb');

INSERT INTO permissions (code, name, description, id) VALUES ('organization.manage', 'Manage organizations', 'Create and change organization structures.', '96789d89-af68-4afb-8812-c23f3ba27566');

INSERT INTO permissions (code, name, description, id) VALUES ('people.read', 'Read people', 'View people records within authorized organization scope.', '7184005e-7c38-444d-910b-ea9e4cc56c41');

INSERT INTO permissions (code, name, description, id) VALUES ('people.manage', 'Manage people', 'Create and change people records within authorized scope.', 'e72fd0d1-e438-4e1d-8a2b-c4c46ec5ab35');

INSERT INTO permissions (code, name, description, id) VALUES ('users.read', 'Read users', 'View system-user identities within authorized scope.', 'fd4aff78-b160-4224-946f-7188e012bdbe');

INSERT INTO permissions (code, name, description, id) VALUES ('users.manage', 'Manage users', 'Create, activate, deactivate, or update system users.', '688875d7-02fc-4584-aa01-ae1ca17f9500');

INSERT INTO permissions (code, name, description, id) VALUES ('access.read', 'Read access', 'View roles, permissions, and access assignments.', 'a531292d-3935-408c-97b5-71b376e1535b');

INSERT INTO permissions (code, name, description, id) VALUES ('access.manage', 'Manage access', 'Manage roles, permissions, and access assignments.', '7042355f-64a2-43b1-99a2-bca437239ba2');

UPDATE alembic_version SET version_num='20260909_0003' WHERE alembic_version.version_num = '20260909_0002';

-- Running upgrade 20260909_0003 -> 20260909_0004

CREATE TABLE audit_events (
    actor_user_id UUID, 
    actor_identifier VARCHAR(320), 
    organization_id UUID, 
    action VARCHAR(100) NOT NULL, 
    resource_type VARCHAR(120) NOT NULL, 
    resource_id VARCHAR(160) NOT NULL, 
    before_state JSON, 
    after_state JSON, 
    event_metadata JSON, 
    source VARCHAR(40) DEFAULT 'api' NOT NULL, 
    request_id VARCHAR(64), 
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    id UUID NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);

CREATE INDEX ix_audit_events_actor_user_id ON audit_events (actor_user_id);

CREATE INDEX ix_audit_events_organization_id ON audit_events (organization_id);

CREATE INDEX ix_audit_events_action ON audit_events (action);

CREATE INDEX ix_audit_events_resource_type ON audit_events (resource_type);

CREATE INDEX ix_audit_events_resource_id ON audit_events (resource_id);

CREATE INDEX ix_audit_events_request_id ON audit_events (request_id);

CREATE INDEX ix_audit_events_occurred_at ON audit_events (occurred_at);

INSERT INTO permissions (id, code, name, description) VALUES ('841895dd-08a9-4a16-a52f-175e8247c603', 'audit.read', 'Read audit history', 'View immutable audit events within authorized organization scope.');

CREATE OR REPLACE FUNCTION prevent_audit_events_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events are immutable';
        END;
        $$ LANGUAGE plpgsql;;

CREATE TRIGGER trg_audit_events_immutable
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_events_mutation();;

UPDATE alembic_version SET version_num='20260909_0004' WHERE alembic_version.version_num = '20260909_0003';

-- Running upgrade 20260909_0004 -> 20260909_0005

CREATE TABLE storage_objects (
    provider VARCHAR(40) NOT NULL, 
    object_path VARCHAR(500) NOT NULL, 
    checksum VARCHAR(128), 
    size_bytes INTEGER NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    UNIQUE (object_path)
);

CREATE TABLE documents (
    title VARCHAR(300) NOT NULL, 
    document_type VARCHAR(100) NOT NULL, 
    status VARCHAR(40) NOT NULL, 
    organization_id UUID NOT NULL, 
    created_by UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE TABLE document_versions (
    document_id UUID NOT NULL, 
    storage_object_id UUID NOT NULL, 
    version_number INTEGER NOT NULL, 
    file_name VARCHAR(300) NOT NULL, 
    mime_type VARCHAR(120) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE RESTRICT, 
    FOREIGN KEY(storage_object_id) REFERENCES storage_objects (id) ON DELETE RESTRICT, 
    UNIQUE (document_id, version_number)
);

CREATE TABLE document_links (
    document_id UUID NOT NULL, 
    entity_type VARCHAR(100) NOT NULL, 
    entity_id VARCHAR(100) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE RESTRICT
);

CREATE TABLE document_permissions (
    document_id UUID NOT NULL, 
    role_id UUID NOT NULL, 
    permission_type VARCHAR(50) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE RESTRICT, 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT
);

INSERT INTO permissions (id, code, name, description) VALUES ('3d9742c0-bc9d-4592-92c3-e3c1d9e5a234', 'documents.read', 'Read documents', 'View documents within authorized organization scope.');

INSERT INTO permissions (id, code, name, description) VALUES ('6cb31a03-1438-426b-8b8e-c92f1ce3bf28', 'documents.manage', 'Manage documents', 'Create and manage documents within authorized organization scope.');

CREATE INDEX ix_documents_organization_id ON documents (organization_id);

CREATE INDEX ix_documents_created_by ON documents (created_by);

CREATE INDEX ix_document_versions_document_id ON document_versions (document_id);

CREATE INDEX ix_document_links_entity_lookup ON document_links (entity_type, entity_id);

CREATE INDEX ix_document_permissions_document_id ON document_permissions (document_id);

UPDATE alembic_version SET version_num='20260909_0005' WHERE alembic_version.version_num = '20260909_0004';

-- Running upgrade 20260909_0005 -> 20260909_0006

ALTER TABLE document_versions ADD COLUMN created_by UUID;

ALTER TABLE document_versions ADD CONSTRAINT fk_document_versions_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT;

CREATE INDEX ix_document_versions_created_by ON document_versions (created_by);

DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM document_versions WHERE created_by IS NULL) THEN
                RAISE EXCEPTION 'B5.2 migration requires explicit created_by remediation for existing document_versions';
            END IF;
        END $$;

ALTER TABLE document_versions ALTER COLUMN created_by SET NOT NULL;

UPDATE alembic_version SET version_num='20260909_0006' WHERE alembic_version.version_num = '20260909_0005';

-- Running upgrade 20260909_0006 -> 20260909_0007

ALTER TABLE document_links ADD COLUMN is_active BOOLEAN DEFAULT true NOT NULL;

ALTER TABLE document_links ALTER COLUMN is_active DROP DEFAULT;

ALTER TABLE document_links ADD CONSTRAINT uq_document_link_target UNIQUE (document_id, entity_type, entity_id);

CREATE INDEX ix_document_links_entity_active ON document_links (entity_type, entity_id, is_active);

CREATE INDEX ix_document_links_document_active ON document_links (document_id, is_active);

CREATE INDEX ix_documents_organization_status ON documents (organization_id, status);

UPDATE alembic_version SET version_num='20260909_0007' WHERE alembic_version.version_num = '20260909_0006';

-- Running upgrade 20260909_0007 -> 20260910_0008

DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM document_permissions LIMIT 1) THEN
                RAISE EXCEPTION
                    'B5.4 activates document_permissions; review and remediate existing rows before migration';
            END IF;
        END $$;;

ALTER TABLE document_permissions ADD CONSTRAINT uq_document_permission_role_type UNIQUE (document_id, role_id, permission_type);

CREATE INDEX ix_document_permissions_document_active_type ON document_permissions (document_id, is_active, permission_type);

CREATE INDEX ix_document_permissions_role_active ON document_permissions (role_id, is_active);

UPDATE alembic_version SET version_num='20260910_0008' WHERE alembic_version.version_num = '20260909_0007';

-- Running upgrade 20260910_0008 -> 20260910_0009

CREATE INDEX ix_documents_document_type ON documents (document_type);

UPDATE alembic_version SET version_num='20260910_0009' WHERE alembic_version.version_num = '20260910_0008';

-- Running upgrade 20260910_0009 -> 20260910_0010

CREATE TABLE document_categories (
    organization_id UUID NOT NULL, 
    code VARCHAR(100) NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    description VARCHAR(500), 
    parent_id UUID, 
    is_active BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_document_category_parent_not_self CHECK (parent_id IS NULL OR parent_id <> id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(parent_id) REFERENCES document_categories (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_document_category_org_code UNIQUE (organization_id, code)
);

CREATE INDEX ix_document_categories_organization_id ON document_categories (organization_id);

CREATE INDEX ix_document_categories_parent_id ON document_categories (parent_id);

CREATE INDEX ix_document_categories_org_active ON document_categories (organization_id, is_active);

CREATE INDEX ix_document_categories_parent_active ON document_categories (parent_id, is_active);

CREATE TABLE document_retention_policies (
    organization_id UUID NOT NULL, 
    code VARCHAR(100) NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    description VARCHAR(500), 
    retention_days INTEGER NOT NULL, 
    basis VARCHAR(40) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_document_retention_days_positive CHECK (retention_days > 0), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_document_retention_policy_org_code UNIQUE (organization_id, code)
);

CREATE INDEX ix_document_retention_policies_organization_id ON document_retention_policies (organization_id);

CREATE INDEX ix_document_retention_policies_org_active ON document_retention_policies (organization_id, is_active);

ALTER TABLE documents ADD COLUMN description TEXT;

ALTER TABLE documents ADD COLUMN priority VARCHAR(40) DEFAULT 'normal' NOT NULL;

ALTER TABLE documents ADD COLUMN category_id UUID;

ALTER TABLE documents ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE documents ADD COLUMN retention_policy_id UUID;

ALTER TABLE documents ADD COLUMN retention_review_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE documents ADD CONSTRAINT fk_documents_category_id FOREIGN KEY(category_id) REFERENCES document_categories (id) ON DELETE RESTRICT;

ALTER TABLE documents ADD CONSTRAINT fk_documents_retention_policy_id FOREIGN KEY(retention_policy_id) REFERENCES document_retention_policies (id) ON DELETE RESTRICT;

CREATE INDEX ix_documents_category_id ON documents (category_id);

CREATE INDEX ix_documents_retention_policy_id ON documents (retention_policy_id);

CREATE INDEX ix_documents_category_status ON documents (category_id, status);

CREATE INDEX ix_documents_expires_at ON documents (expires_at);

CREATE INDEX ix_documents_retention_review_at ON documents (retention_review_at);

CREATE INDEX ix_documents_priority ON documents (priority);

UPDATE alembic_version SET version_num='20260910_0010' WHERE alembic_version.version_num = '20260910_0009';

-- Running upgrade 20260910_0010 -> 20260910_0011

ALTER TABLE roles ADD COLUMN organization_id UUID;

ALTER TABLE roles ADD CONSTRAINT fk_roles_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT;

CREATE INDEX ix_roles_organization_id ON roles (organization_id);

UPDATE alembic_version SET version_num='20260910_0011' WHERE alembic_version.version_num = '20260910_0010';

-- Running upgrade 20260910_0011 -> 20260910_0012

CREATE TABLE user_sessions (
    user_id UUID NOT NULL, 
    refresh_token_hash VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    last_used_at TIMESTAMP WITH TIME ZONE, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT fk_user_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id);

CREATE UNIQUE INDEX ix_user_sessions_refresh_token_hash ON user_sessions (refresh_token_hash);

CREATE INDEX ix_user_sessions_expires_at ON user_sessions (expires_at);

CREATE INDEX ix_user_sessions_revoked_at ON user_sessions (revoked_at);

UPDATE alembic_version SET version_num='20260910_0012' WHERE alembic_version.version_num = '20260910_0011';

-- Running upgrade 20260910_0012 -> 20260911_0013

CREATE TYPE workflow_definition_scope_mode AS ENUM ('SELF', 'SELF_AND_DESCENDANTS');

CREATE TYPE workflow_definition_status AS ENUM ('DRAFT', 'PUBLISHED', 'RETIRED');

CREATE TABLE workflow_definitions (
    organization_id UUID NOT NULL, 
    code VARCHAR(100) NOT NULL, 
    name VARCHAR(180) NOT NULL, 
    description VARCHAR(1000), 
    version INTEGER NOT NULL, 
    scope_mode workflow_definition_scope_mode NOT NULL, 
    status workflow_definition_status NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_workflow_definition_version_positive CHECK (version > 0), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_workflow_definition_org_code_version UNIQUE (organization_id, code, version)
);

CREATE INDEX ix_workflow_definitions_organization_id ON workflow_definitions (organization_id);

CREATE INDEX ix_workflow_definitions_status ON workflow_definitions (status);

CREATE INDEX ix_workflow_definitions_org_code_status ON workflow_definitions (organization_id, code, status);

CREATE TABLE workflow_states (
    definition_id UUID NOT NULL, 
    code VARCHAR(100) NOT NULL, 
    name VARCHAR(180) NOT NULL, 
    position INTEGER NOT NULL, 
    is_initial BOOLEAN DEFAULT false NOT NULL, 
    is_terminal BOOLEAN DEFAULT false NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_workflow_state_position_nonnegative CHECK (position >= 0), 
    FOREIGN KEY(definition_id) REFERENCES workflow_definitions (id) ON DELETE CASCADE, 
    CONSTRAINT uq_workflow_state_definition_code UNIQUE (definition_id, code)
);

CREATE INDEX ix_workflow_states_definition_id ON workflow_states (definition_id);

CREATE INDEX ix_workflow_states_definition_position ON workflow_states (definition_id, position);

CREATE TABLE workflow_transitions (
    definition_id UUID NOT NULL, 
    code VARCHAR(100) NOT NULL, 
    name VARCHAR(180) NOT NULL, 
    from_state_id UUID NOT NULL, 
    to_state_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_workflow_transition_not_self CHECK (from_state_id <> to_state_id), 
    FOREIGN KEY(definition_id) REFERENCES workflow_definitions (id) ON DELETE CASCADE, 
    FOREIGN KEY(from_state_id) REFERENCES workflow_states (id) ON DELETE RESTRICT, 
    FOREIGN KEY(to_state_id) REFERENCES workflow_states (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_workflow_transition_definition_code UNIQUE (definition_id, code)
);

CREATE INDEX ix_workflow_transitions_definition_id ON workflow_transitions (definition_id);

CREATE INDEX ix_workflow_transitions_from_state_id ON workflow_transitions (from_state_id);

CREATE INDEX ix_workflow_transitions_to_state_id ON workflow_transitions (to_state_id);

CREATE INDEX ix_workflow_transitions_definition_from ON workflow_transitions (definition_id, from_state_id);

CREATE TYPE workflow_instance_status AS ENUM ('ACTIVE', 'COMPLETED', 'CANCELLED');

CREATE TABLE workflow_instances (
    definition_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    resource_type VARCHAR(100) NOT NULL, 
    resource_id VARCHAR(160) NOT NULL, 
    current_state_id UUID NOT NULL, 
    status workflow_instance_status NOT NULL, 
    started_by_user_id UUID NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    cancelled_at TIMESTAMP WITH TIME ZONE, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(definition_id) REFERENCES workflow_definitions (id) ON DELETE RESTRICT, 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(current_state_id) REFERENCES workflow_states (id) ON DELETE RESTRICT, 
    FOREIGN KEY(started_by_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_workflow_instance_definition_resource UNIQUE (definition_id, organization_id, resource_type, resource_id)
);

CREATE INDEX ix_workflow_instances_definition_id ON workflow_instances (definition_id);

CREATE INDEX ix_workflow_instances_organization_id ON workflow_instances (organization_id);

CREATE INDEX ix_workflow_instances_current_state_id ON workflow_instances (current_state_id);

CREATE INDEX ix_workflow_instances_status ON workflow_instances (status);

CREATE INDEX ix_workflow_instances_started_by_user_id ON workflow_instances (started_by_user_id);

CREATE INDEX ix_workflow_instances_org_status ON workflow_instances (organization_id, status);

CREATE INDEX ix_workflow_instances_resource ON workflow_instances (resource_type, resource_id);

CREATE TABLE workflow_transition_records (
    instance_id UUID NOT NULL, 
    transition_id UUID NOT NULL, 
    from_state_id UUID NOT NULL, 
    to_state_id UUID NOT NULL, 
    actor_user_id UUID NOT NULL, 
    comment TEXT, 
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(instance_id) REFERENCES workflow_instances (id) ON DELETE RESTRICT, 
    FOREIGN KEY(transition_id) REFERENCES workflow_transitions (id) ON DELETE RESTRICT, 
    FOREIGN KEY(from_state_id) REFERENCES workflow_states (id) ON DELETE RESTRICT, 
    FOREIGN KEY(to_state_id) REFERENCES workflow_states (id) ON DELETE RESTRICT, 
    FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_workflow_transition_records_instance_id ON workflow_transition_records (instance_id);

CREATE INDEX ix_workflow_transition_records_transition_id ON workflow_transition_records (transition_id);

CREATE INDEX ix_workflow_transition_records_actor_user_id ON workflow_transition_records (actor_user_id);

CREATE INDEX ix_workflow_transition_records_instance_occurred ON workflow_transition_records (instance_id, occurred_at);

INSERT INTO permissions (id, code, name, description) VALUES ('52756787-8102-4d12-8b4d-5674a5677fcf', 'workflow.read', 'Read workflows', 'View workflow definitions and instances within authorized organization scope.');

INSERT INTO permissions (id, code, name, description) VALUES ('31e6e933-8003-4f88-8256-6adb77bee56c', 'workflow.manage', 'Manage workflows', 'Create, version, publish, and retire workflow definitions within authorized scope.');

INSERT INTO permissions (id, code, name, description) VALUES ('1d292e2a-a0b0-41bd-88ff-5a9dbed5b0bd', 'workflow.execute', 'Execute workflows', 'Start and advance workflow instances within authorized organization scope.');

INSERT INTO role_permissions (role_id, permission_id, created_at, updated_at)
        SELECT r.id, p.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.code = 'super_admin'
          AND p.code IN ('workflow.read', 'workflow.manage', 'workflow.execute')
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          );;

CREATE OR REPLACE FUNCTION prevent_workflow_transition_record_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'workflow_transition_records are immutable';
        END;
        $$ LANGUAGE plpgsql;;

CREATE TRIGGER trg_workflow_transition_records_immutable
        BEFORE UPDATE OR DELETE ON workflow_transition_records
        FOR EACH ROW
        EXECUTE FUNCTION prevent_workflow_transition_record_mutation();;

UPDATE alembic_version SET version_num='20260911_0013' WHERE alembic_version.version_num = '20260910_0012';

-- Running upgrade 20260911_0013 -> 20260911_0014

CREATE TYPE notification_severity AS ENUM ('INFO', 'SUCCESS', 'WARNING', 'CRITICAL');

CREATE TABLE notifications (
    recipient_user_id UUID NOT NULL, 
    organization_id UUID, 
    event_code VARCHAR(120) NOT NULL, 
    source VARCHAR(100) NOT NULL, 
    severity notification_severity NOT NULL, 
    title VARCHAR(180) NOT NULL, 
    body TEXT, 
    resource_type VARCHAR(100), 
    resource_id VARCHAR(160), 
    action_path VARCHAR(500), 
    dedupe_key VARCHAR(180), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    read_at TIMESTAMP WITH TIME ZONE, 
    id UUID NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(recipient_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_notifications_recipient_dedupe_key UNIQUE (recipient_user_id, dedupe_key)
);

CREATE INDEX ix_notifications_recipient_user_id ON notifications (recipient_user_id);

CREATE INDEX ix_notifications_organization_id ON notifications (organization_id);

CREATE INDEX ix_notifications_event_code ON notifications (event_code);

CREATE INDEX ix_notifications_source ON notifications (source);

CREATE INDEX ix_notifications_severity ON notifications (severity);

CREATE INDEX ix_notifications_resource_type ON notifications (resource_type);

CREATE INDEX ix_notifications_resource_id ON notifications (resource_id);

CREATE INDEX ix_notifications_created_at ON notifications (created_at);

CREATE INDEX ix_notifications_read_at ON notifications (read_at);

CREATE INDEX ix_notifications_recipient_created ON notifications (recipient_user_id, created_at);

CREATE INDEX ix_notifications_recipient_read_created ON notifications (recipient_user_id, read_at, created_at);

CREATE INDEX ix_notifications_organization_created ON notifications (organization_id, created_at);

CREATE OR REPLACE FUNCTION protect_notification_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'notifications cannot be physically deleted';
            END IF;

            IF NEW.recipient_user_id IS DISTINCT FROM OLD.recipient_user_id
               OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
               OR NEW.event_code IS DISTINCT FROM OLD.event_code
               OR NEW.source IS DISTINCT FROM OLD.source
               OR NEW.severity IS DISTINCT FROM OLD.severity
               OR NEW.title IS DISTINCT FROM OLD.title
               OR NEW.body IS DISTINCT FROM OLD.body
               OR NEW.resource_type IS DISTINCT FROM OLD.resource_type
               OR NEW.resource_id IS DISTINCT FROM OLD.resource_id
               OR NEW.action_path IS DISTINCT FROM OLD.action_path
               OR NEW.dedupe_key IS DISTINCT FROM OLD.dedupe_key
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.id IS DISTINCT FROM OLD.id THEN
                RAISE EXCEPTION 'notification content and ownership are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;;

CREATE TRIGGER trg_notifications_protected
        BEFORE UPDATE OR DELETE ON notifications
        FOR EACH ROW
        EXECUTE FUNCTION protect_notification_mutation();;

UPDATE alembic_version SET version_num='20260911_0014' WHERE alembic_version.version_num = '20260911_0013';

-- Running upgrade 20260911_0014 -> 20260911_0015

CREATE TYPE hr_job_profile_scope_mode AS ENUM ('SELF', 'SELF_AND_DESCENDANTS');

CREATE TABLE hr_job_profiles (
    organization_id UUID NOT NULL, 
    code VARCHAR(100) NOT NULL, 
    title VARCHAR(180) NOT NULL, 
    description VARCHAR(1000), 
    scope_mode hr_job_profile_scope_mode NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_hr_job_profile_org_code UNIQUE (organization_id, code)
);

CREATE INDEX ix_hr_job_profiles_organization_id ON hr_job_profiles (organization_id);

CREATE INDEX ix_hr_job_profiles_org_active ON hr_job_profiles (organization_id, is_active);

CREATE TABLE hr_positions (
    organization_id UUID NOT NULL, 
    job_profile_id UUID NOT NULL, 
    code VARCHAR(100) NOT NULL, 
    name VARCHAR(180), 
    reports_to_position_id UUID, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_hr_position_reports_to_not_self CHECK (reports_to_position_id IS NULL OR reports_to_position_id <> id), 
    FOREIGN KEY(job_profile_id) REFERENCES hr_job_profiles (id) ON DELETE RESTRICT, 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(reports_to_position_id) REFERENCES hr_positions (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_hr_position_org_code UNIQUE (organization_id, code)
);

CREATE INDEX ix_hr_positions_organization_id ON hr_positions (organization_id);

CREATE INDEX ix_hr_positions_job_profile_id ON hr_positions (job_profile_id);

CREATE INDEX ix_hr_positions_reports_to_position_id ON hr_positions (reports_to_position_id);

CREATE INDEX ix_hr_positions_org_active ON hr_positions (organization_id, is_active);

CREATE TYPE hr_employment_type AS ENUM ('PERMANENT', 'FIXED_TERM', 'PART_TIME', 'CONTRACTOR', 'INTERN', 'OTHER');

CREATE TABLE hr_employments (
    organization_id UUID NOT NULL, 
    person_id UUID NOT NULL, 
    position_id UUID, 
    employment_number VARCHAR(80), 
    employment_type hr_employment_type NOT NULL, 
    start_date DATE NOT NULL, 
    end_date DATE, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_hr_employment_date_range CHECK (end_date IS NULL OR end_date >= start_date), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(person_id) REFERENCES people (id) ON DELETE RESTRICT, 
    FOREIGN KEY(position_id) REFERENCES hr_positions (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_hr_employment_org_number UNIQUE (organization_id, employment_number)
);

CREATE INDEX ix_hr_employments_organization_id ON hr_employments (organization_id);

CREATE INDEX ix_hr_employments_person_id ON hr_employments (person_id);

CREATE INDEX ix_hr_employments_position_id ON hr_employments (position_id);

CREATE INDEX ix_hr_employments_employment_type ON hr_employments (employment_type);

CREATE INDEX ix_hr_employments_org_active ON hr_employments (organization_id, is_active);

CREATE INDEX ix_hr_employments_person_org_active ON hr_employments (person_id, organization_id, is_active);

INSERT INTO permissions (id, code, name, description) VALUES ('cbe7a519-acc4-4bbb-ac33-922264f5b1c4', 'hr.read', 'Read HR foundation', 'View HR job profiles, planned positions, and employment records within authorized organization scope.');

INSERT INTO permissions (id, code, name, description) VALUES ('fad014a2-914d-48f2-ab58-d2b0b851abef', 'hr.manage', 'Manage HR foundation', 'Create and manage HR job profiles, positions, and employment records within authorized organization scope.');

UPDATE alembic_version SET version_num='20260911_0015' WHERE alembic_version.version_num = '20260911_0014';

-- Running upgrade 20260911_0015 -> 20260911_0016

CREATE TYPE customer_crm_customer_type AS ENUM ('INDIVIDUAL', 'HOUSEHOLD', 'BUSINESS', 'RETAIL', 'WHOLESALE', 'OTHER');

CREATE TYPE customer_crm_commercial_status AS ENUM ('PROSPECT', 'ACTIVE', 'INACTIVE', 'BLOCKED', 'ARCHIVED');

CREATE TYPE customer_crm_source AS ENUM ('MANUAL', 'COMMERCE_ACTIVITY', 'PHONE_ORDER', 'IMPORT', 'OTHER');

CREATE TABLE customer_crm_records (
    organization_id UUID NOT NULL, 
    commerce_customer_ref VARCHAR(128) NOT NULL, 
    customer_type customer_crm_customer_type NOT NULL, 
    commercial_status customer_crm_commercial_status NOT NULL, 
    source customer_crm_source NOT NULL, 
    display_label VARCHAR(200) NOT NULL, 
    assigned_owner_user_id UUID, 
    created_by_user_id UUID NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(assigned_owner_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_customer_crm_org_commerce_ref UNIQUE (organization_id, commerce_customer_ref)
);

CREATE INDEX ix_customer_crm_records_organization_id ON customer_crm_records (organization_id);

CREATE INDEX ix_customer_crm_records_customer_type ON customer_crm_records (customer_type);

CREATE INDEX ix_customer_crm_records_commercial_status ON customer_crm_records (commercial_status);

CREATE INDEX ix_customer_crm_records_source ON customer_crm_records (source);

CREATE INDEX ix_customer_crm_records_assigned_owner_user_id ON customer_crm_records (assigned_owner_user_id);

CREATE INDEX ix_customer_crm_records_created_by_user_id ON customer_crm_records (created_by_user_id);

CREATE INDEX ix_customer_crm_org_active_status ON customer_crm_records (organization_id, is_active, commercial_status);

CREATE TABLE customer_tags (
    organization_id UUID NOT NULL, 
    name VARCHAR(60) NOT NULL, 
    normalized_name VARCHAR(60) NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_by_user_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_customer_tag_org_name UNIQUE (organization_id, normalized_name)
);

CREATE INDEX ix_customer_tags_organization_id ON customer_tags (organization_id);

CREATE INDEX ix_customer_tags_created_by_user_id ON customer_tags (created_by_user_id);

CREATE INDEX ix_customer_tags_org_active ON customer_tags (organization_id, is_active);

CREATE TABLE customer_notes (
    customer_crm_record_id UUID NOT NULL, 
    author_user_id UUID NOT NULL, 
    body VARCHAR(4000) NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(customer_crm_record_id) REFERENCES customer_crm_records (id) ON DELETE CASCADE, 
    FOREIGN KEY(author_user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_customer_notes_customer_crm_record_id ON customer_notes (customer_crm_record_id);

CREATE INDEX ix_customer_notes_author_user_id ON customer_notes (author_user_id);

CREATE INDEX ix_customer_notes_customer_created ON customer_notes (customer_crm_record_id, created_at);

CREATE TABLE customer_crm_tags (
    customer_crm_record_id UUID NOT NULL, 
    tag_id UUID NOT NULL, 
    created_by_user_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (customer_crm_record_id, tag_id), 
    FOREIGN KEY(customer_crm_record_id) REFERENCES customer_crm_records (id) ON DELETE CASCADE, 
    FOREIGN KEY(tag_id) REFERENCES customer_tags (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_customer_crm_tags_created_by_user_id ON customer_crm_tags (created_by_user_id);

INSERT INTO permissions (id, code, name, description) VALUES ('164ea78a-05b5-4793-8d9a-c19075d319c1', 'crm.customer.read', 'Read customer CRM', 'View organization-scoped customer CRM metadata and references.');

INSERT INTO permissions (id, code, name, description) VALUES ('03f859fa-e915-40c1-a2aa-1ba52d2d402c', 'crm.customer.manage', 'Manage customer CRM', 'Create and change organization-scoped customer CRM metadata.');

INSERT INTO permissions (id, code, name, description) VALUES ('9d53d49f-ec38-44eb-8624-d9792e78ce89', 'crm.customer.notes.read', 'Read customer notes', 'View customer CRM notes within authorized organization scope.');

INSERT INTO permissions (id, code, name, description) VALUES ('a7d204f8-bc6e-422d-b7d0-819a8d2b07d9', 'crm.customer.notes.manage', 'Manage customer notes', 'Create and edit customer CRM notes within authorized organization scope.');

INSERT INTO permissions (id, code, name, description) VALUES ('6ce4f5da-63cb-44e1-8bda-1c78f1f92ed7', 'crm.customer.assign', 'Assign customer owners', 'Assign or unassign internal owners for customer CRM records.');

INSERT INTO permissions (id, code, name, description) VALUES ('5b6ee1b2-3380-43e2-9e41-5a51a0ce02f5', 'crm.customer.tags.manage', 'Manage customer tags', 'Create and attach organization-owned CRM tags.');

INSERT INTO permissions (id, code, name, description) VALUES ('656f4232-4072-4554-9449-e7a7bf3fc31f', 'crm.customer.commerce_activity.read', 'Read customer commerce activity', 'View authorized commerce activity projections for customer CRM records.');

UPDATE alembic_version SET version_num='20260911_0016' WHERE alembic_version.version_num = '20260911_0015';

-- Running upgrade 20260911_0016 -> 20260911_0017

CREATE TYPE supplier_kind AS ENUM ('COMPANY', 'INDIVIDUAL', 'OTHER');

CREATE TYPE supplier_commercial_status AS ENUM ('PROSPECT', 'ACTIVE', 'INACTIVE', 'SUSPENDED', 'ARCHIVED');

CREATE TYPE supplier_source AS ENUM ('MANUAL', 'IMPORT', 'ACCOUNTING_REFERENCE', 'PROCUREMENT_REFERENCE', 'OTHER');

CREATE TABLE supplier_profiles (
    organization_id UUID NOT NULL, 
    supplier_kind supplier_kind NOT NULL, 
    display_name VARCHAR(200) NOT NULL, 
    commercial_status supplier_commercial_status NOT NULL, 
    source supplier_source NOT NULL, 
    assigned_owner_user_id UUID, 
    created_by_user_id UUID NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(assigned_owner_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_supplier_profiles_organization_id ON supplier_profiles (organization_id);

CREATE INDEX ix_supplier_profiles_supplier_kind ON supplier_profiles (supplier_kind);

CREATE INDEX ix_supplier_profiles_commercial_status ON supplier_profiles (commercial_status);

CREATE INDEX ix_supplier_profiles_source ON supplier_profiles (source);

CREATE INDEX ix_supplier_profiles_assigned_owner_user_id ON supplier_profiles (assigned_owner_user_id);

CREATE INDEX ix_supplier_profiles_created_by_user_id ON supplier_profiles (created_by_user_id);

CREATE INDEX ix_supplier_profiles_org_active_status ON supplier_profiles (organization_id, is_active, commercial_status);

CREATE TABLE supplier_representatives (
    supplier_id UUID NOT NULL, 
    display_name VARCHAR(200) NOT NULL, 
    job_title VARCHAR(120), 
    phone VARCHAR(32), 
    email VARCHAR(254), 
    is_primary BOOLEAN DEFAULT false NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(supplier_id) REFERENCES supplier_profiles (id) ON DELETE CASCADE
);

CREATE INDEX ix_supplier_representatives_supplier_id ON supplier_representatives (supplier_id);

CREATE INDEX ix_supplier_representatives_supplier_active ON supplier_representatives (supplier_id, is_active);

CREATE UNIQUE INDEX uq_supplier_representative_active_primary ON supplier_representatives (supplier_id) WHERE is_primary IS TRUE AND is_active IS TRUE;

CREATE TABLE supplier_tags (
    organization_id UUID NOT NULL, 
    name VARCHAR(60) NOT NULL, 
    normalized_name VARCHAR(60) NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_by_user_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_supplier_tag_org_name UNIQUE (organization_id, normalized_name)
);

CREATE INDEX ix_supplier_tags_organization_id ON supplier_tags (organization_id);

CREATE INDEX ix_supplier_tags_created_by_user_id ON supplier_tags (created_by_user_id);

CREATE INDEX ix_supplier_tags_org_active ON supplier_tags (organization_id, is_active);

CREATE TABLE supplier_notes (
    supplier_id UUID NOT NULL, 
    author_user_id UUID NOT NULL, 
    body VARCHAR(4000) NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(supplier_id) REFERENCES supplier_profiles (id) ON DELETE CASCADE, 
    FOREIGN KEY(author_user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_supplier_notes_supplier_id ON supplier_notes (supplier_id);

CREATE INDEX ix_supplier_notes_author_user_id ON supplier_notes (author_user_id);

CREATE INDEX ix_supplier_notes_supplier_created ON supplier_notes (supplier_id, created_at);

CREATE TABLE supplier_profile_tags (
    supplier_id UUID NOT NULL, 
    tag_id UUID NOT NULL, 
    created_by_user_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (supplier_id, tag_id), 
    FOREIGN KEY(supplier_id) REFERENCES supplier_profiles (id) ON DELETE CASCADE, 
    FOREIGN KEY(tag_id) REFERENCES supplier_tags (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_supplier_profile_tags_created_by_user_id ON supplier_profile_tags (created_by_user_id);

CREATE TYPE supplier_external_system AS ENUM ('ACCOUNTING', 'ERP', 'PROCUREMENT', 'OTHER');

CREATE TABLE supplier_external_references (
    supplier_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    system supplier_external_system NOT NULL, 
    external_id VARCHAR(128) NOT NULL, 
    normalized_external_id VARCHAR(128) NOT NULL, 
    created_by_user_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(supplier_id) REFERENCES supplier_profiles (id) ON DELETE CASCADE, 
    FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_supplier_external_ref_org_system_id UNIQUE (organization_id, system, normalized_external_id)
);

CREATE INDEX ix_supplier_external_references_supplier_id ON supplier_external_references (supplier_id);

CREATE INDEX ix_supplier_external_references_organization_id ON supplier_external_references (organization_id);

CREATE INDEX ix_supplier_external_references_system ON supplier_external_references (system);

CREATE INDEX ix_supplier_external_references_created_by_user_id ON supplier_external_references (created_by_user_id);

CREATE INDEX ix_supplier_external_refs_supplier ON supplier_external_references (supplier_id, system);

INSERT INTO permissions (id, code, name, description) VALUES ('f9c69ef1-28b1-4e11-a321-f64e657e4c50', 'supplier.read', 'Read suppliers', 'View organization-scoped supplier operational metadata.');

INSERT INTO permissions (id, code, name, description) VALUES ('6793ea7f-01c6-4b24-8958-cd1e4522b58e', 'supplier.manage', 'Manage suppliers', 'Create and update organization-scoped supplier operational metadata.');

INSERT INTO permissions (id, code, name, description) VALUES ('d7e76c68-3678-4590-91de-87ccdf540387', 'supplier.representative.read', 'Read supplier representatives', 'View supplier representatives in authorized supplier scope.');

INSERT INTO permissions (id, code, name, description) VALUES ('97d801ef-0c14-4662-bc06-9149ac0a7447', 'supplier.representative.manage', 'Manage supplier representatives', 'Create and update supplier representatives in authorized supplier scope.');

INSERT INTO permissions (id, code, name, description) VALUES ('8922e620-a8c2-4444-ab7b-11fa7467f2fb', 'supplier.representative.contact.read', 'Read supplier representative contacts', 'View unmasked representative phone and email values.');

INSERT INTO permissions (id, code, name, description) VALUES ('4749d267-8487-4cb6-ad16-fa3769bde0e2', 'supplier.notes.read', 'Read supplier notes', 'View supplier notes within authorized organization scope.');

INSERT INTO permissions (id, code, name, description) VALUES ('392dc5a6-d2a4-475d-8d6c-bd500e02aa63', 'supplier.notes.manage', 'Manage supplier notes', 'Create and edit supplier notes within authorized organization scope.');

INSERT INTO permissions (id, code, name, description) VALUES ('08f3118d-f433-461a-b79f-3e623bd67d72', 'supplier.assign', 'Assign supplier owners', 'Assign or unassign internal owners for supplier records.');

INSERT INTO permissions (id, code, name, description) VALUES ('fe15d03d-cada-4578-a6d1-801676d8b725', 'supplier.tags.catalog.manage', 'Manage supplier tag catalog', 'Create organization-owned supplier tag vocabulary.');

INSERT INTO permissions (id, code, name, description) VALUES ('e506cfa3-3daa-4ba8-a568-da7283d036f6', 'supplier.tags.assign', 'Assign supplier tags', 'Attach or remove existing organization-owned tags on suppliers.');

INSERT INTO permissions (id, code, name, description) VALUES ('1d7aac19-0bf0-4283-978c-9fd817ea9249', 'supplier.external_reference.read', 'Read supplier external references', 'View supplier external-system reference metadata.');

INSERT INTO permissions (id, code, name, description) VALUES ('5a77a5f1-9d77-4719-a180-8e1740f71f7a', 'supplier.external_reference.manage', 'Manage supplier external references', 'Create and remove supplier external-system references.');

UPDATE alembic_version SET version_num='20260911_0017' WHERE alembic_version.version_num = '20260911_0016';

COMMIT;

