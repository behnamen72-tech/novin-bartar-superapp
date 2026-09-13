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

compile("components/core/WorkflowManagementView.tsx");
compile("lib/workflow-management.ts");
compile("lib/core-types.ts");
compile("lib/navigation.ts");

const component = fs.readFileSync(path.join(root, "components/core/WorkflowManagementView.tsx"), "utf8");
const helper = fs.readFileSync(path.join(root, "lib/workflow-management.ts"), "utf8");
const page = fs.readFileSync(path.join(root, "app/page.tsx"), "utf8");
const nav = fs.readFileSync(path.join(root, "lib/navigation.ts"), "utf8");
const permissions = fs.readFileSync(path.join(root, "lib/permissions.ts"), "utf8");
const proxy = fs.readFileSync(path.join(root, "lib/authenticated-backend.ts"), "utf8");

ok(/key: "workflow"/.test(nav), "workflow navigation item missing");
ok(/workflow\.read/.test(nav) && /workflow\.manage/.test(nav) && /workflow\.execute/.test(nav));
ok(/WorkflowManagementView/.test(page));
ok(/activeView === "workflow"/.test(page));
ok(/"workflow\.read": "مشاهده گردش‌کارها"/.test(permissions));
ok(/availableTransitions/.test(helper));
ok(/normalizeWorkflowCode/.test(helper));
ok(/workflowDefinitionStatusLabels/.test(helper));
ok(/api\/core\/workflow\/organizations/.test(component));
ok(/include_drafts=/.test(component));
ok(/api\/core\/workflow\/instances/.test(component));
ok(/\/states/.test(component));
ok(/\/transitions/.test(component));
ok(/definitionAction\("publish"\)/.test(component));
ok(/definitionAction\("retire"\)/.test(component));
ok(/definitionAction\("new-version"\)/.test(component));
ok(/workflow\.read لازم است/.test(component));
ok(/تمام کنترل‌های امنیتی دوباره در Backend اعمال می‌شوند/.test(component));
ok(/proxyAuthenticatedRequest/.test(proxy));
ok(/rejectCrossSiteMutation/.test(proxy));

const routes = [
  "app/api/core/workflow/definitions/route.ts",
  "app/api/core/workflow/definitions/[definitionId]/route.ts",
  "app/api/core/workflow/definitions/[definitionId]/states/[stateId]/route.ts",
  "app/api/core/workflow/definitions/[definitionId]/transitions/[transitionId]/route.ts",
  "app/api/core/workflow/definitions/[definitionId]/publish/route.ts",
  "app/api/core/workflow/definitions/[definitionId]/retire/route.ts",
  "app/api/core/workflow/definitions/[definitionId]/new-version/route.ts",
  "app/api/core/workflow/instances/route.ts",
  "app/api/core/workflow/instances/[instanceId]/transition/route.ts",
  "app/api/core/workflow/instances/[instanceId]/cancel/route.ts",
  "app/api/core/workflow/organizations/route.ts",
];
for (const route of routes) {
  const source = fs.readFileSync(path.join(root, route), "utf8");
  ok(/proxyAuthenticated(Get|Request)/.test(source), `${route} bypasses authenticated proxy`);
}

for (const route of routes.filter((item) => item.includes("["))) {
  const source = fs.readFileSync(path.join(root, route), "utf8");
  ok(/encodeURIComponent/.test(source), `${route} does not encode dynamic path identifiers`);
}

console.log(`C1 workflow UI checks passed (${assertions} assertions).`);
