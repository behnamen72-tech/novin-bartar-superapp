const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const assert = require("node:assert/strict");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const work = fs.mkdtempSync(path.join(os.tmpdir(), "novin-bartar-b65-"));

function compile(relativePath, outputName) {
  const source = fs.readFileSync(path.join(root, relativePath), "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.CommonJS,
      strict: true,
      jsx: ts.JsxEmit.ReactJSX,
    },
    fileName: relativePath,
    reportDiagnostics: true,
  });
  const diagnostics = (output.diagnostics ?? []).filter(
    (item) => item.category === ts.DiagnosticCategory.Error,
  );
  assert.equal(diagnostics.length, 0, `${relativePath} contains TypeScript diagnostics`);
  fs.writeFileSync(path.join(work, outputName), output.outputText);
}

try {
  compile("lib/organization-management.ts", "organization-management.js");
  const management = require(path.join(work, "organization-management.js"));

  const organizations = [
    { id: "h", name: "Holding", code: "H", organization_type: "holding", parent_id: null, is_active: true },
    { id: "c", name: "Company", code: "C", organization_type: "company", parent_id: "h", is_active: true },
    { id: "b", name: "Branch", code: "B", organization_type: "branch", parent_id: "c", is_active: true },
    { id: "u", name: "Unit", code: "U", organization_type: "unit", parent_id: "b", is_active: true },
  ];
  const descendantManager = [{
    role_code: "admin",
    organization_id: "h",
    organization_name: "Holding",
    scope_mode: "self_and_descendants",
    permissions: ["organization.manage"],
  }];
  const selfManager = [{
    role_code: "manager",
    organization_id: "c",
    organization_name: "Company",
    scope_mode: "self",
    permissions: ["organization.manage"],
  }];

  assert.deepEqual(management.allowedChildTypes("holding"), ["company"]);
  assert.deepEqual(management.allowedChildTypes("company"), ["branch", "unit"]);
  assert.deepEqual(management.allowedChildTypes("branch"), ["unit"]);
  assert.deepEqual(management.allowedChildTypes("unit"), []);
  assert.equal(management.canManageOrganization("u", organizations, descendantManager), true);
  assert.equal(management.canManageOrganization("b", organizations, selfManager), false);
  assert.equal(management.canManageOrganization("c", organizations, selfManager), true);
  assert.equal(management.canCreateChildUnder("c", organizations, selfManager), false);
  assert.equal(management.canCreateChildUnder("c", organizations, descendantManager), true);
  assert.equal(management.hasActiveChildren("c", organizations), true);
  assert.equal(management.normalizedOrganizationCode("  co-12  "), "CO-12");

  const inactiveParent = organizations.map((item) =>
    item.id === "c" ? { ...item, is_active: false } : item,
  );
  assert.equal(management.canManageOrganization("b", inactiveParent, descendantManager), false);
  assert.equal(management.canActivateOrganization({ ...organizations[2], is_active: false }, inactiveParent), false);
  assert.equal(management.canActivateOrganization({ ...organizations[2], is_active: false }, organizations), true);

  const route = fs.readFileSync(path.join(root, "app/api/core/organizations/route.ts"), "utf8");
  const itemRoute = fs.readFileSync(path.join(root, "app/api/core/organizations/[organizationId]/route.ts"), "utf8");
  const statusRoute = fs.readFileSync(path.join(root, "app/api/core/organizations/[organizationId]/status/route.ts"), "utf8");
  const page = fs.readFileSync(path.join(root, "app/page.tsx"), "utf8");
  assert.match(route, /proxyAuthenticatedRequest\("\/organizations", request\)/);
  assert.match(itemRoute, /proxyAuthenticatedRequest/);
  assert.match(statusRoute, /\/status/);
  assert.match(page, /include_inactive=true/);

  console.log("B6.5 organization-management checks passed (18 assertions).\n");
} finally {
  fs.rmSync(work, { recursive: true, force: true });
}
