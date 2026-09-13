const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const assert = require("node:assert/strict");
const ts = require("typescript");
const cp = require("node:child_process");

const root = path.resolve(__dirname, "..");
const work = fs.mkdtempSync(path.join(os.tmpdir(), "novin-bartar-b67-"));
let assertions = 0;

function ok(value, message) {
  assert.ok(value, message);
  assertions += 1;
}
function equal(actual, expected, message) {
  assert.equal(actual, expected, message);
  assertions += 1;
}
function deepEqual(actual, expected, message) {
  assert.deepEqual(actual, expected, message);
  assertions += 1;
}
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
  equal(diagnostics.length, 0, `${relativePath} contains TypeScript diagnostics`);
  fs.writeFileSync(path.join(work, outputName), output.outputText);
}

try {
  compile("lib/document-management.ts", "document-management.js");
  compile("components/core/DocumentManagementView.tsx", "DocumentManagementView.js");

  const helperSource = fs
    .readFileSync(path.join(root, "lib/document-management.ts"), "utf8")
    .replace('from "@/lib/organization-management"', 'from "./organization-management"')
    .replace(/from "@\/lib\/core-types";/g, 'from "./core-types";');
  const orgSource = fs
    .readFileSync(path.join(root, "lib/organization-management.ts"), "utf8")
    .replace(/from "@\/lib\/core-types";/g, 'from "./core-types";');
  fs.writeFileSync(path.join(work, "core-types.ts"), fs.readFileSync(path.join(root, "lib/core-types.ts"), "utf8"));
  fs.writeFileSync(path.join(work, "organization-management.ts"), orgSource);
  fs.writeFileSync(path.join(work, "document-management.ts"), helperSource);
  fs.writeFileSync(path.join(work, "tsconfig.json"), JSON.stringify({
    compilerOptions: { target: "ES2022", module: "CommonJS", strict: true, skipLibCheck: true, outDir: "./out" },
    include: ["./*.ts"],
  }));
  cp.execFileSync("tsc", ["-p", path.join(work, "tsconfig.json")], { stdio: "pipe" });
  const management = require(path.join(work, "out", "document-management.js"));

  const organizations = [
    { id: "h", name: "Holding", code: "H", organization_type: "holding", parent_id: null, is_active: true },
    { id: "c1", name: "Company 1", code: "C1", organization_type: "company", parent_id: "h", is_active: true },
    { id: "c2", name: "Company 2", code: "C2", organization_type: "company", parent_id: "h", is_active: true },
    { id: "b1", name: "Branch 1", code: "B1", organization_type: "branch", parent_id: "c1", is_active: true },
  ];
  const assignments = [{ role_code: "docs", organization_id: "c1", organization_name: "Company 1", scope_mode: "self_and_descendants", permissions: ["documents.read", "documents.manage"] }];
  equal(management.canManageDocumentsForOrganization("c1", organizations, assignments), true);
  equal(management.canManageDocumentsForOrganization("b1", organizations, assignments), true);
  equal(management.canManageDocumentsForOrganization("c2", organizations, assignments), false);
  deepEqual(management.manageableDocumentOrganizations(organizations, assignments).map((item) => item.id), ["c1", "b1"]);
  equal(management.documentStatusLabels.archived, "بایگانی‌شده");
  equal(management.formatFileSize(1024), "1.0 KB");

  const route = fs.readFileSync(path.join(root, "app/api/core/documents/route.ts"), "utf8");
  const detailRoute = fs.readFileSync(path.join(root, "app/api/core/documents/[documentId]/route.ts"), "utf8");
  const metadataRoute = fs.readFileSync(path.join(root, "app/api/core/documents/[documentId]/metadata/route.ts"), "utf8");
  const versionsRoute = fs.readFileSync(path.join(root, "app/api/core/documents/[documentId]/versions/route.ts"), "utf8");
  const downloadRoute = fs.readFileSync(path.join(root, "app/api/core/documents/[documentId]/download/route.ts"), "utf8");
  const linksRoute = fs.readFileSync(path.join(root, "app/api/core/documents/[documentId]/links/route.ts"), "utf8");
  const permissionsRoute = fs.readFileSync(path.join(root, "app/api/core/documents/[documentId]/permissions/route.ts"), "utf8");
  const permissionItemRoute = fs.readFileSync(path.join(root, "app/api/core/documents/[documentId]/permissions/[permissionId]/route.ts"), "utf8");
  const categoryRoute = fs.readFileSync(path.join(root, "app/api/core/document-categories/route.ts"), "utf8");
  const retentionRoute = fs.readFileSync(path.join(root, "app/api/core/document-retention-policies/route.ts"), "utf8");
  const proxy = fs.readFileSync(path.join(root, "lib/authenticated-backend.ts"), "utf8");
  const client = fs.readFileSync(path.join(root, "lib/api-client.ts"), "utf8");
  const page = fs.readFileSync(path.join(root, "app/page.tsx"), "utf8");
  const nav = fs.readFileSync(path.join(root, "lib/navigation.ts"), "utf8");
  const component = fs.readFileSync(path.join(root, "components/core/DocumentManagementView.tsx"), "utf8");

  ok(/proxyAuthenticatedRequest\("\/documents", request\)/.test(route));
  ok(/proxyAuthenticatedGet/.test(detailRoute));
  ok(/\/metadata/.test(metadataRoute));
  ok(/\/versions/.test(versionsRoute));
  ok(/proxyAuthenticatedDownload/.test(downloadRoute));
  ok(/\/links/.test(linksRoute));
  ok(/proxyAuthenticatedGet/.test(permissionsRoute));
  ok(/proxyAuthenticatedRequest/.test(permissionsRoute));
  ok(/permissionId/.test(permissionItemRoute));
  ok(/proxyAuthenticatedRequest/.test(permissionItemRoute));
  ok(/proxyAuthenticatedRequest\("\/document-categories", request\)/.test(categoryRoute));
  ok(/proxyAuthenticatedRequest\("\/document-retention-policies", request\)/.test(retentionRoute));
  ok(/Cache-Control", "no-store, private"/.test(proxy));
  ok(/Content-Disposition/.test(proxy));
  ok(/export async function apiDownload/.test(client));
  ok(/novin-bartar:session-expired/.test(client));
  ok(/key: "documents"/.test(nav));
  ok(/DocumentManagementView/.test(page));
  ok(/allPermissions\.includes\("documents\.manage"\)/.test(component));
  ok(/datetime-local/.test(component));
  ok(/new Date\(expiresAt\)\.toISOString\(\)/.test(component));
  ok(/accept=\{ALLOWED_UPLOADS\}/.test(component));
  ok(/archive|restore/.test(component));
  ok(/document-categories/.test(component));
  ok(/document-retention-policies/.test(component));
  ok(/entity_type/.test(component));
  ok(/timeline/.test(component));
  ok(/documentPermissions\.length === 0/.test(component));
  ok(/ACL سند فقط دسترسی سازمانی موجود را محدودتر می‌کند/.test(component));
  ok(/access\.manage/.test(component));
  ok(/اولین ACL باید از نوع مدیریت/.test(component));
  ok(/DocumentPermissionType/.test(component));

  console.log(`B6.7 documents-management checks passed (${assertions} assertions).\n`);
} finally {
  fs.rmSync(work, { recursive: true, force: true });
}
