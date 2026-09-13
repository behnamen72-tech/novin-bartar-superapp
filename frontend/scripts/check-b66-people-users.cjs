const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const assert = require("node:assert/strict");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const work = fs.mkdtempSync(path.join(os.tmpdir(), "novin-bartar-b66-"));
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
  compile("lib/people-user-management.ts", "people-user-management.js");
  // The helper imports organization-management through the alias, so compile a
  // standalone variant with that import rewritten to a local module for runtime checks.
  const helperSource = fs
    .readFileSync(path.join(root, "lib/people-user-management.ts"), "utf8")
    .replace('from "@/lib/organization-management"', 'from "./organization-management"')
    .replace(/from "@\/lib\/core-types";/g, 'from "./core-types";');
  const orgSource = fs
    .readFileSync(path.join(root, "lib/organization-management.ts"), "utf8")
    .replace(/from "@\/lib\/core-types";/g, 'from "./core-types";');
  fs.writeFileSync(path.join(work, "core-types.ts"), fs.readFileSync(path.join(root, "lib/core-types.ts"), "utf8"));
  fs.writeFileSync(path.join(work, "organization-management.ts"), orgSource);
  fs.writeFileSync(path.join(work, "people-user-management.ts"), helperSource);

  const config = {
    compilerOptions: {
      target: "ES2022",
      module: "CommonJS",
      strict: true,
      esModuleInterop: true,
      skipLibCheck: true,
      outDir: "./out",
    },
    include: ["./*.ts"],
  };
  fs.writeFileSync(path.join(work, "tsconfig.json"), JSON.stringify(config));
  const cp = require("node:child_process");
  cp.execFileSync("tsc", ["-p", path.join(work, "tsconfig.json")], { stdio: "pipe" });
  const management = require(path.join(work, "out", "people-user-management.js"));

  const organizations = [
    { id: "h", name: "Holding", code: "H", organization_type: "holding", parent_id: null, is_active: true },
    { id: "c1", name: "Company 1", code: "C1", organization_type: "company", parent_id: "h", is_active: true },
    { id: "c2", name: "Company 2", code: "C2", organization_type: "company", parent_id: "h", is_active: true },
    { id: "b1", name: "Branch 1", code: "B1", organization_type: "branch", parent_id: "c1", is_active: true },
  ];
  const holdingPeopleManager = [{ role_code: "admin", organization_id: "h", organization_name: "Holding", scope_mode: "self_and_descendants", permissions: ["people.manage", "users.manage"] }];
  const companyPeopleManager = [{ role_code: "manager", organization_id: "c1", organization_name: "Company 1", scope_mode: "self_and_descendants", permissions: ["people.manage", "users.manage"] }];
  const selfOnlyManager = [{ role_code: "self", organization_id: "c1", organization_name: "Company 1", scope_mode: "self", permissions: ["people.manage"] }];

  equal(management.canManageOrganizationForPermission("b1", "people.manage", organizations, companyPeopleManager), true);
  equal(management.canManageOrganizationForPermission("c2", "people.manage", organizations, companyPeopleManager), false);
  equal(management.canManageOrganizationForPermission("b1", "people.manage", organizations, selfOnlyManager), false);
  deepEqual(management.manageableOrganizationsForPermission("people.manage", organizations, companyPeopleManager).map((item) => item.id), ["c1", "b1"]);

  const sharedPerson = {
    id: "p1", first_name: "A", last_name: "B", email: null, phone: null, is_active: true,
    relationships: [
      { id: "r1", organization_id: "c1", organization_name: "Company 1", relationship_code: "employee", start_date: null, end_date: null, is_active: true },
      { id: "r2", organization_id: "c2", organization_name: "Company 2", relationship_code: "contractor", start_date: null, end_date: null, is_active: true },
    ],
  };
  equal(management.canManagePersonGlobally(sharedPerson, "people.manage", organizations, companyPeopleManager), false);
  equal(management.canManagePersonGlobally(sharedPerson, "people.manage", organizations, holdingPeopleManager), true);

  const localPerson = { ...sharedPerson, id: "p2", relationships: [sharedPerson.relationships[0]] };
  equal(management.canManagePersonGlobally(localPerson, "users.manage", organizations, companyPeopleManager), true);
  equal(management.normalizedOptionalText("   "), null);
  equal(management.normalizedOptionalText("  a@b.test "), "a@b.test");
  equal(management.normalizedUsername("  Admin.One "), "admin.one");
  equal(management.normalizedUsername("   "), null);

  const users = [{ id: "u1", person_id: "p1", person_name: "A B", email: "a@b.test", username: null, is_active: true, last_login_at: null, organization_names: ["Company 1"] }];
  deepEqual(management.eligiblePeopleForUserCreation([sharedPerson, localPerson], users, organizations, companyPeopleManager).map((item) => item.id), ["p2"]);

  const peopleRoute = fs.readFileSync(path.join(root, "app/api/core/people/route.ts"), "utf8");
  const peopleItem = fs.readFileSync(path.join(root, "app/api/core/people/[personId]/route.ts"), "utf8");
  const peopleStatus = fs.readFileSync(path.join(root, "app/api/core/people/[personId]/status/route.ts"), "utf8");
  const relRoute = fs.readFileSync(path.join(root, "app/api/core/people/[personId]/relationships/route.ts"), "utf8");
  const relStatus = fs.readFileSync(path.join(root, "app/api/core/people/[personId]/relationships/[relationshipId]/status/route.ts"), "utf8");
  const usersRoute = fs.readFileSync(path.join(root, "app/api/core/users/route.ts"), "utf8");
  const usersItem = fs.readFileSync(path.join(root, "app/api/core/users/[userId]/route.ts"), "utf8");
  const usersStatus = fs.readFileSync(path.join(root, "app/api/core/users/[userId]/status/route.ts"), "utf8");
  const passwordRoute = fs.readFileSync(path.join(root, "app/api/core/users/[userId]/password-reset/route.ts"), "utf8");

  ok(/proxyAuthenticatedRequest\("\/people", request\)/.test(peopleRoute));
  ok(/proxyAuthenticatedRequest/.test(peopleItem));
  ok(/\/status/.test(peopleStatus));
  ok(/\/relationships/.test(relRoute));
  ok(/relationshipId/.test(relStatus));
  ok(/proxyAuthenticatedRequest\("\/users", request\)/.test(usersRoute));
  ok(/proxyAuthenticatedRequest/.test(usersItem));
  ok(/\/status/.test(usersStatus));
  ok(/password-reset/.test(passwordRoute));

  const peopleComponent = fs.readFileSync(path.join(root, "components/core/PeopleManagementView.tsx"), "utf8");
  const userComponent = fs.readFileSync(path.join(root, "components/core/UserManagementView.tsx"), "utf8");
  const page = fs.readFileSync(path.join(root, "app/page.tsx"), "utf8");
  const types = fs.readFileSync(path.join(root, "lib/core-types.ts"), "utf8");

  ok(/canManagePersonGlobally/.test(peopleComponent));
  ok(/person\.relationship\.status|relationships/.test(peopleComponent));
  ok(/type="date"/.test(peopleComponent));
  ok(/passwordConfirm/.test(userComponent));
  ok(/autoComplete="new-password"/.test(userComponent));
  ok(/currentUser\.id/.test(userComponent));
  ok(/closeEditor/.test(userComponent));
  ok(/ownPerson/.test(peopleComponent));
  ok(/PeopleManagementView/.test(page));
  ok(/UserManagementView/.test(page));
  ok(/allPermissions\.includes\("people\.read"\)/.test(page));
  ok(/allPermissions\.includes\("organization\.read"\)/.test(page));
  ok(/id: string;\s+organization_id: string;/.test(types));
  ok(/start_date: string \| null;/.test(types));
  ok(/end_date: string \| null;/.test(types));

  console.log(`B6.6 people/user-management checks passed (${assertions} assertions).\n`);
} finally {
  fs.rmSync(work, { recursive: true, force: true });
}
