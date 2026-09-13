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
  "components/core/SearchManagementView.tsx",
  "components/app/AppShell.tsx",
  "lib/core-types.ts",
  "lib/navigation.ts",
  "app/page.tsx",
  "app/api/core/search/route.ts",
];
for (const target of compileTargets) compile(target);

const nav = read("lib/navigation.ts");
const shell = read("components/app/AppShell.tsx");
const page = read("app/page.tsx");
const component = read("components/core/SearchManagementView.tsx");
const route = read("app/api/core/search/route.ts");
const css = read("app/globals.css");

ok(/key: "search"/.test(nav), "search navigation item missing");
ok(!/key: "search"[\s\S]*requiredAny/.test(nav.split('key: "search"')[1]?.split('key: "access"')[0] ?? ""), "search should derive access from domain permissions, not a standalone UI permission");
ok(/navigate\("search"\)/.test(shell), "topbar search button does not open search view");
ok(/SearchManagementView/.test(page), "search view is not mounted");
ok(/activeView === "search"/.test(page), "search active view branch missing");
ok(/api\/core\/search\?q=\$\{encodeURIComponent\(normalized\)\}/.test(component), "search query is not URL-encoded");
ok(/limit_per_type=12/.test(component), "search per-domain result cap missing");
ok(/result\.entity_type/.test(component) || /item\.entity_type/.test(component), "search result type is not used");
ok(/proxyAuthenticatedGet/.test(route), "search BFF route bypasses authenticated proxy");
ok(/\.global-search-button/.test(css), "topbar search styling missing");
ok(/\.search-result-card/.test(css), "search result styling missing");
ok(/حداقل دو کاراکتر/.test(component), "minimum query guidance missing");
ok(/واقعاً مجوز مشاهده/.test(component), "permission-aware search guidance missing");

console.log(`C3 search UI checks passed (${assertions} assertions).`);
