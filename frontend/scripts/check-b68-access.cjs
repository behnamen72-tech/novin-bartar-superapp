const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
let assertions = 0;
function ok(value, message) { assert.ok(value, message); assertions += 1; }
function equal(actual, expected, message) { assert.equal(actual, expected, message); assertions += 1; }
function compile(relativePath) {
  const source = fs.readFileSync(path.join(root, relativePath), "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, strict: true, jsx: ts.JsxEmit.ReactJSX },
    fileName: relativePath,
    reportDiagnostics: true,
  });
  const diagnostics = (output.diagnostics ?? []).filter((item) => item.category === ts.DiagnosticCategory.Error);
  equal(diagnostics.length, 0, `${relativePath} contains TypeScript diagnostics`);
}

compile("components/core/AccessManagementView.tsx");
compile("lib/people-user-management.ts");
compile("lib/core-types.ts");

const component = fs.readFileSync(path.join(root, "components/core/AccessManagementView.tsx"), "utf8");
const page = fs.readFileSync(path.join(root, "app/page.tsx"), "utf8");
const rolesRoute = fs.readFileSync(path.join(root, "app/api/core/access/roles/route.ts"), "utf8");
const roleItem = fs.readFileSync(path.join(root, "app/api/core/access/roles/[roleId]/route.ts"), "utf8");
const roleStatus = fs.readFileSync(path.join(root, "app/api/core/access/roles/[roleId]/status/route.ts"), "utf8");
const rolePermission = fs.readFileSync(path.join(root, "app/api/core/access/roles/[roleId]/permissions/[permissionCode]/route.ts"), "utf8");
const assignmentRoute = fs.readFileSync(path.join(root, "app/api/core/access/assignments/route.ts"), "utf8");
const assignmentStatus = fs.readFileSync(path.join(root, "app/api/core/access/assignments/[assignmentId]/status/route.ts"), "utf8");
const permissionRoute = fs.readFileSync(path.join(root, "app/api/core/access/permissions/route.ts"), "utf8");
const helper = fs.readFileSync(path.join(root, "lib/people-user-management.ts"), "utf8");

ok(/proxyAuthenticatedRequest\("\/access\/roles", request\)/.test(rolesRoute));
ok(/proxyAuthenticatedRequest/.test(roleItem));
ok(/\/status/.test(roleStatus));
ok(/permissionCode/.test(rolePermission));
ok(/method: currentlyGranted \? "DELETE" : "POST"/.test(component));
ok(/proxyAuthenticatedRequest\("\/access\/assignments", request\)/.test(assignmentRoute));
ok(/assignmentId/.test(assignmentStatus));
ok(/proxyAuthenticatedGet\("\/access\/permissions"/.test(permissionRoute));
ok(/AccessManagementView/.test(page));
ok(/access\.manage/.test(component));
ok(/last effective access manager/.test(component));
ok(/Privilege Escalation/.test(component));
ok(/scope_mode/.test(component));
ok(/datetime-local/.test(component));
ok(/role\.is_system/.test(component));
ok(/role\.organization_id !== null/.test(component));
ok(/permission: "people.manage" \| "users.manage" \| "access.manage"/.test(helper));
ok(/api\/core\/access-overview/.test(component));
ok(/allPermissions\.includes\(permission\.code\)/.test(component));
ok(/Target user must have an active person relationship/.test(component));
ok(/canManageOrganizationForPermission\(item\.organization_id, "access\.manage"/.test(component));
ok(/canManageOrganizationForPermission\(role\.organization_id, "access\.manage"/.test(component));
ok(/encodeURIComponent\(roleId\)/.test(roleItem));
ok(/encodeURIComponent\(permissionCode\)/.test(rolePermission));
ok(/encodeURIComponent\(assignmentId\)/.test(assignmentStatus));

const documentAcl = fs.readFileSync(path.join(root, "components/core/DocumentManagementView.tsx"), "utf8");
const documentAclRoute = fs.readFileSync(path.join(root, "app/api/core/documents/[documentId]/permissions/route.ts"), "utf8");
ok(/ACL سند فقط دسترسی سازمانی موجود را محدودتر می‌کند/.test(documentAcl));
ok(/access\.manage.*اجازه مشاهده یا دانلود/s.test(documentAcl));
ok(/proxyAuthenticatedRequest/.test(documentAclRoute));
ok(/بازیابی ACL سند/.test(component));
ok(/شناسه UUID سند/.test(component));
ok(/access\.manage.*حق مشاهده یا دانلود/s.test(component));
ok(/api\/core\/documents\/\$\{encodeURIComponent\(documentId\)\}\/permissions/.test(component));
ok(/recoveryPermissions\.length === 0 \? "manage"/.test(component));

console.log(`B6.8 access-management checks passed (${assertions} assertions).`);
