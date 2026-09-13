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
  "components/modules/HRFoundationView.tsx",
  "lib/hr-management.ts",
  "lib/core-types.ts",
  "lib/navigation.ts",
  "app/page.tsx",
  "app/api/modules/hr/organizations/route.ts",
  "app/api/modules/hr/job-profiles/route.ts",
  "app/api/modules/hr/job-profiles/[profileId]/route.ts",
  "app/api/modules/hr/job-profiles/[profileId]/status/route.ts",
  "app/api/modules/hr/positions/route.ts",
  "app/api/modules/hr/positions/[positionId]/route.ts",
  "app/api/modules/hr/positions/[positionId]/status/route.ts",
  "app/api/modules/hr/people/route.ts",
  "app/api/modules/hr/employments/route.ts",
  "app/api/modules/hr/employments/[employmentId]/route.ts",
  "app/api/modules/hr/employments/[employmentId]/status/route.ts",
];
for (const target of compileTargets) compile(target);

const nav = read("lib/navigation.ts");
const page = read("app/page.tsx");
const shell = read("components/app/AppShell.tsx");
const component = read("components/modules/HRFoundationView.tsx");
const css = read("app/globals.css");

ok(/key: "hr"/.test(nav), "HR navigation item missing");
ok(/requiredAny: \["hr\.read", "hr\.manage"\]/.test(nav), "HR navigation permission guard missing");
ok(/HRFoundationView/.test(page), "HR foundation view is not mounted");
ok(/activeView === "hr"/.test(page), "HR active-view branch missing");
ok(/<strong>D[1-9]<\/strong>/.test(shell), "sidebar phase marker is not a D-phase checkpoint");
ok(/پست سازمانی را می‌توان قبل از استخدام افراد ساخت/.test(component), "future-structure guidance missing");
ok(/api\/modules\/hr\/organizations/.test(component), "HR organization capabilities are not loaded");
ok(/api\/modules\/hr\/job-profiles/.test(component), "job profile UI is not wired");
ok(/api\/modules\/hr\/positions/.test(component), "position UI is not wired");
ok(/api\/modules\/hr\/employments/.test(component), "employment UI is not wired");
ok(/api\/modules\/hr\/people/.test(component), "HR person picker is not wired");
ok(/پست خالی/.test(component), "planned vacancy signal missing");
ok(/سابقه باقی می‌ماند/.test(component), "employment history/non-delete guidance missing");
ok(/\.hr-foundation/.test(css), "HR foundation styling missing");

const writeRoutes = [
  "app/api/modules/hr/job-profiles/route.ts",
  "app/api/modules/hr/job-profiles/[profileId]/route.ts",
  "app/api/modules/hr/job-profiles/[profileId]/status/route.ts",
  "app/api/modules/hr/positions/route.ts",
  "app/api/modules/hr/positions/[positionId]/route.ts",
  "app/api/modules/hr/positions/[positionId]/status/route.ts",
  "app/api/modules/hr/employments/route.ts",
  "app/api/modules/hr/employments/[employmentId]/route.ts",
  "app/api/modules/hr/employments/[employmentId]/status/route.ts",
];
for (const route of writeRoutes) {
  ok(/proxyAuthenticatedRequest/.test(read(route)), `${route} bypasses centralized mutation proxy`);
}
const dynamic = [
  ["app/api/modules/hr/job-profiles/[profileId]/route.ts", "profileId"],
  ["app/api/modules/hr/job-profiles/[profileId]/status/route.ts", "profileId"],
  ["app/api/modules/hr/positions/[positionId]/route.ts", "positionId"],
  ["app/api/modules/hr/positions/[positionId]/status/route.ts", "positionId"],
  ["app/api/modules/hr/employments/[employmentId]/route.ts", "employmentId"],
  ["app/api/modules/hr/employments/[employmentId]/status/route.ts", "employmentId"],
];
for (const [route, param] of dynamic) {
  ok(new RegExp(`encodeURIComponent\\(${param}\\)`).test(read(route)), `${route} does not encode dynamic ID`);
}
for (const route of [
  "app/api/modules/hr/organizations/route.ts",
  "app/api/modules/hr/people/route.ts",
]) {
  ok(/proxyAuthenticatedGet/.test(read(route)), `${route} bypasses authenticated read proxy`);
}

console.log(`D1 HR foundation UI checks passed (${assertions} assertions).`);
