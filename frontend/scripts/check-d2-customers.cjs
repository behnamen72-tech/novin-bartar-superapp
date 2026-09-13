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
  equal(diagnostics.length, 0, `${relativePath} contains TypeScript syntax diagnostics`);
}

const compileTargets = [
  "components/modules/CustomerCRMView.tsx",
  "lib/crm-management.ts",
  "lib/core-types.ts",
  "lib/navigation.ts",
  "lib/permissions.ts",
  "app/page.tsx",
  "components/core/SearchManagementView.tsx",
  "app/api/modules/customers/organizations/route.ts",
  "app/api/modules/customers/assignees/route.ts",
  "app/api/modules/customers/customers/route.ts",
  "app/api/modules/customers/customers/[customerId]/route.ts",
  "app/api/modules/customers/customers/[customerId]/status/route.ts",
  "app/api/modules/customers/customers/[customerId]/assign/route.ts",
  "app/api/modules/customers/customers/[customerId]/unassign/route.ts",
  "app/api/modules/customers/customers/[customerId]/tags/[tagId]/route.ts",
  "app/api/modules/customers/customers/[customerId]/notes/route.ts",
  "app/api/modules/customers/customers/[customerId]/notes/[noteId]/route.ts",
  "app/api/modules/customers/customers/[customerId]/commerce-activity/route.ts",
  "app/api/modules/customers/customer-tags/route.ts",
];
for (const target of compileTargets) compile(target);

const nav = read("lib/navigation.ts");
const page = read("app/page.tsx");
const shell = read("components/app/AppShell.tsx");
const component = read("components/modules/CustomerCRMView.tsx");
const search = read("components/core/SearchManagementView.tsx");
const css = read("app/globals.css");
const permissions = read("lib/permissions.ts");

ok(/key: "customers"/.test(nav), "customer CRM navigation item missing");
ok(/crm\.customer\.read/.test(nav), "customer CRM navigation permission guard missing");
ok(/CustomerCRMView/.test(page), "CustomerCRMView is not mounted");
ok(/activeView === "customers"/.test(page), "customer CRM active-view branch missing");
ok(/<strong>D[2-9]<\/strong>/.test(shell), "sidebar phase marker is before D2");
ok(/هویت، ورود و رمز مشتری متعلق به فروشگاه مجازی/.test(component), "commerce identity boundary guidance missing");
ok(/api\/modules\/customers\/organizations/.test(component), "CRM organization capabilities are not loaded");
ok(/api\/modules\/customers\/customers/.test(component), "CRM customer API is not wired");
ok(/api\/modules\/customers\/assignees/.test(component), "least-privilege assignee picker is not wired");
ok(/api\/modules\/customers\/customer-tags/.test(component), "CRM tags API is not wired");
ok(/commerce-activity/.test(component), "commerce activity projection is not wired");
ok(/محتوای یادداشت وارد Audit نمی‌شود/.test(component), "free-text Audit exclusion guidance missing");
ok(/expected_version/.test(component), "optimistic concurrency version is not sent by UI");
ok(/customer: "customers"/.test(search), "global search does not navigate customer results to CRM");
ok(/customer: "مشتری"/.test(search), "global search customer label missing");
ok(/crm\.customer\.commerce_activity\.read/.test(permissions), "commerce-activity permission label missing");
ok(/\.crm-view/.test(css), "CRM foundation styling missing");

const writeRoutes = [
  "app/api/modules/customers/customers/route.ts",
  "app/api/modules/customers/customers/[customerId]/route.ts",
  "app/api/modules/customers/customers/[customerId]/status/route.ts",
  "app/api/modules/customers/customers/[customerId]/assign/route.ts",
  "app/api/modules/customers/customers/[customerId]/unassign/route.ts",
  "app/api/modules/customers/customers/[customerId]/tags/[tagId]/route.ts",
  "app/api/modules/customers/customers/[customerId]/notes/route.ts",
  "app/api/modules/customers/customers/[customerId]/notes/[noteId]/route.ts",
  "app/api/modules/customers/customer-tags/route.ts",
];
for (const route of writeRoutes) {
  ok(/proxyAuthenticatedRequest/.test(read(route)), `${route} bypasses centralized mutation proxy`);
}

for (const route of [
  "app/api/modules/customers/organizations/route.ts",
  "app/api/modules/customers/assignees/route.ts",
  "app/api/modules/customers/customers/[customerId]/commerce-activity/route.ts",
]) {
  ok(/proxyAuthenticatedGet/.test(read(route)), `${route} bypasses authenticated read proxy`);
}

for (const [route, param] of [
  ["app/api/modules/customers/customers/[customerId]/route.ts", "customerId"],
  ["app/api/modules/customers/customers/[customerId]/status/route.ts", "customerId"],
  ["app/api/modules/customers/customers/[customerId]/assign/route.ts", "customerId"],
  ["app/api/modules/customers/customers/[customerId]/unassign/route.ts", "customerId"],
  ["app/api/modules/customers/customers/[customerId]/notes/route.ts", "customerId"],
  ["app/api/modules/customers/customers/[customerId]/commerce-activity/route.ts", "customerId"],
  ["app/api/modules/customers/customers/[customerId]/notes/[noteId]/route.ts", "noteId"],
  ["app/api/modules/customers/customers/[customerId]/tags/[tagId]/route.ts", "tagId"],
]) {
  ok(new RegExp(`encodeURIComponent\\(${param}\\)`).test(read(route)), `${route} does not encode ${param}`);
}

console.log(`D2 Customer CRM UI checks passed (${assertions} assertions).`);
