const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const assert = require("node:assert/strict");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const work = fs.mkdtempSync(path.join(os.tmpdir(), "novin-bartar-b63-"));

function compile(name) {
  const source = fs.readFileSync(path.join(root, "lib", `${name}.ts`), "utf8");
  let output = ts.transpileModule(source, {
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
  compile("navigation");
  const navigation = require(path.join(work, "navigation.js"));

  assert.equal(navigation.isViewKey("dashboard"), true);
  assert.equal(navigation.isViewKey("documents"), true);
  assert.equal(navigation.viewFromLocation("?view=people"), "people");
  assert.equal(navigation.viewFromLocation("?view=unknown"), "dashboard");
  assert.equal(navigation.locationForView("dashboard"), "/");
  assert.equal(navigation.locationForView("access"), "/?view=access");
  assert.equal(navigation.isViewVisible("dashboard", []), true);
  assert.equal(navigation.isViewVisible("organizations", []), false);
  assert.equal(
    navigation.isViewVisible("organizations", ["organization.manage"]),
    true,
  );
  assert.equal(navigation.isViewVisible("audit", ["access.manage"]), false);
  assert.equal(navigation.isViewVisible("audit", ["audit.read"]), true);
  assert.equal(navigation.isViewVisible("search", []), true);

  const sections = navigation.getVisibleNavigation(["users.read", "audit.read"]);
  const keys = sections.flatMap((section) => section.items.map((item) => item.key));
  assert.deepEqual(keys, ["dashboard", "users", "notifications", "search", "audit"]);

  console.log("B6.3 navigation checks passed (13 assertions).");
} finally {
  fs.rmSync(work, { recursive: true, force: true });
}
