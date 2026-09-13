const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
let assertions = 0;
function ok(value, message) { assert.ok(value, message); assertions += 1; }
function equal(actual, expected, message) { assert.equal(actual, expected, message); assertions += 1; }
function read(file) { return fs.readFileSync(path.join(root, file), "utf8"); }
function compile(relativePath) {
  const output = ts.transpileModule(read(relativePath), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, strict: true, jsx: ts.JsxEmit.ReactJSX },
    fileName: relativePath,
    reportDiagnostics: true,
  });
  const diagnostics = (output.diagnostics ?? []).filter((item) => item.category === ts.DiagnosticCategory.Error);
  equal(diagnostics.length, 0, `${relativePath} contains TypeScript syntax diagnostics`);
}

const targets = [
  "components/modules/SupplierFoundationView.tsx",
  "components/core/SearchManagementView.tsx",
  "components/app/AppShell.tsx",
  "lib/core-types.ts",
  "lib/navigation.ts",
  "lib/permissions.ts",
  "app/page.tsx",
  "app/api/modules/suppliers/organizations/route.ts",
  "app/api/modules/suppliers/assignees/route.ts",
  "app/api/modules/suppliers/tags/catalog/route.ts",
  "app/api/modules/suppliers/suppliers/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/status/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/assign/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/unassign/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/representatives/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/representatives/[representativeId]/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/tags/[tagId]/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/notes/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/notes/[noteId]/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/external-references/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/external-references/[referenceId]/route.ts",
];
for (const target of targets) compile(target);

const nav = read("lib/navigation.ts");
const page = read("app/page.tsx");
const shell = read("components/app/AppShell.tsx");
const component = read("components/modules/SupplierFoundationView.tsx");
const search = read("components/core/SearchManagementView.tsx");
const permissions = read("lib/permissions.ts");

ok(/key: "suppliers"/.test(nav), "suppliers navigation missing");
ok(/supplier\.representative\.contact\.read/.test(nav), "contact-read permission missing from navigation guard");
ok(/supplier\.tags\.catalog\.manage/.test(nav), "tag catalog permission missing");
ok(/supplier\.tags\.assign/.test(nav), "tag assignment permission missing");
ok(/SupplierFoundationView/.test(page), "SupplierFoundationView not mounted");
ok(/activeView === "suppliers"/.test(page), "suppliers active view missing");
ok(/<strong>D3<\/strong>/.test(shell), "sidebar phase marker is not D3");
ok(/اطلاعات تماس Mask شده/.test(component), "masked-contact UX guidance missing");
ok(/ساخت Tag و اختصاص Tag دو Permission مستقل/.test(component), "separate tag permission guidance missing");
ok(/NFKC\+trim/.test(component), "external ID normalization guidance missing");
ok(/نماینده اصلی/.test(component), "primary representative UI missing");
ok(/expected_version/.test(component), "optimistic concurrency is not wired");
ok(/supplier: "suppliers"/.test(search), "global search supplier navigation missing");
ok(/supplier: "تأمین‌کننده"/.test(search), "global search supplier label missing");
ok(/supplier\.representative\.contact\.read/.test(permissions), "contact-read permission label missing");

const writeRoutes = [
  "app/api/modules/suppliers/tags/catalog/route.ts",
  "app/api/modules/suppliers/suppliers/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/status/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/assign/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/unassign/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/representatives/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/representatives/[representativeId]/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/tags/[tagId]/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/notes/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/notes/[noteId]/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/external-references/route.ts",
  "app/api/modules/suppliers/suppliers/[supplierId]/external-references/[referenceId]/route.ts",
];
for (const route of writeRoutes) ok(/proxyAuthenticatedRequest/.test(read(route)), `${route} bypasses mutation proxy`);

for (const route of [
  "app/api/modules/suppliers/organizations/route.ts",
  "app/api/modules/suppliers/assignees/route.ts",
]) ok(/proxyAuthenticatedGet/.test(read(route)), `${route} bypasses authenticated read proxy`);

for (const [route, param] of [
  ["app/api/modules/suppliers/suppliers/[supplierId]/route.ts", "supplierId"],
  ["app/api/modules/suppliers/suppliers/[supplierId]/representatives/[representativeId]/route.ts", "representativeId"],
  ["app/api/modules/suppliers/suppliers/[supplierId]/tags/[tagId]/route.ts", "tagId"],
  ["app/api/modules/suppliers/suppliers/[supplierId]/notes/[noteId]/route.ts", "noteId"],
  ["app/api/modules/suppliers/suppliers/[supplierId]/external-references/[referenceId]/route.ts", "referenceId"],
]) ok(new RegExp(`encodeURIComponent\\(${param}\\)`).test(read(route)), `${route} does not encode ${param}`);

console.log(`D3 Supplier Foundation UI checks passed (${assertions} assertions).`);
