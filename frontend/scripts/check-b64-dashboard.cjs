const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const assert = require("node:assert/strict");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const work = fs.mkdtempSync(path.join(os.tmpdir(), "novin-bartar-b64-"));

function compile(name) {
  const source = fs.readFileSync(path.join(root, "lib", `${name}.ts`), "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.CommonJS,
      strict: true,
    },
    fileName: `${name}.ts`,
    reportDiagnostics: true,
  });
  const diagnostics = (output.diagnostics ?? []).filter(
    (item) => item.category === ts.DiagnosticCategory.Error,
  );
  assert.equal(diagnostics.length, 0, `${name}.ts contains TypeScript diagnostics`);

  const javascript = output.outputText.replace(
    'require("@/lib/permissions")',
    'require("./permissions")',
  );
  fs.writeFileSync(path.join(work, `${name}.js`), javascript);
}

try {
  compile("permissions");
  compile("dashboard");
  compile("core-labels");
  const dashboard = require(path.join(work, "dashboard.js"));
  const labels = require(path.join(work, "core-labels.js"));

  assert.deepEqual(dashboard.getDashboardCapabilities([]), {
    organizations: false,
    people: false,
    users: false,
    documents: false,
    audit: false,
  });
  assert.deepEqual(
    dashboard.getDashboardCapabilities([
      "organization.read",
      "people.read",
      "documents.read",
      "audit.read",
    ]),
    {
      organizations: true,
      people: true,
      users: false,
      documents: true,
      audit: true,
    },
  );
  assert.equal(
    dashboard.getDashboardCapabilities(["organization.manage"]).organizations,
    false,
    "dashboard must not call a read endpoint merely because manage is present",
  );

  const snapshot = {
    organizations: [
      { id: "o1", is_active: true },
      { id: "o2", is_active: false },
    ],
    people: [
      { id: "p1", is_active: true },
      { id: "p2", is_active: true },
      { id: "p3", is_active: false },
    ],
    users: [
      { id: "u1", is_active: true },
      { id: "u2", is_active: false },
    ],
    expiringDocuments: [
      { expiration_state: "expiring_soon" },
      { expiration_state: "expired" },
      { expiration_state: "expired" },
    ],
    recentAudit: [],
  };
  const assignments = [
    { role_code: "admin" },
    { role_code: "admin" },
    { role_code: "viewer" },
  ];
  assert.deepEqual(dashboard.summarizeDashboard(snapshot, assignments), {
    organizationCount: 2,
    activeOrganizationCount: 1,
    peopleCount: 3,
    activePeopleCount: 2,
    userCount: 2,
    activeUserCount: 1,
    expiringDocumentCount: 1,
    expiredDocumentCount: 2,
    assignmentCount: 3,
    roleCount: 2,
  });

  assert.equal(labels.auditActionLabel("user.created"), "ایجاد کاربر");
  assert.equal(labels.auditActionLabel("unknown.action"), "unknown.action");
  assert.equal(labels.resourceLabel("document"), "سند");
  assert.equal(labels.resourceLabel("future_type"), "future_type");

  const expired = labels.documentExpirationLabel({
    expiration_state: "expired",
    days_remaining: -4,
  });
  assert.match(expired, /روز گذشته$/);
  assert.equal(
    labels.documentExpirationLabel({
      expiration_state: "expiring_soon",
      days_remaining: 0,
    }),
    "امروز",
  );
  assert.equal(
    labels.documentExpirationLabel({
      expiration_state: "active",
      days_remaining: 12,
    }),
    "فعال",
  );

  console.log("B6.4 dashboard checks passed (11 assertions).\n");
} finally {
  fs.rmSync(work, { recursive: true, force: true });
}
