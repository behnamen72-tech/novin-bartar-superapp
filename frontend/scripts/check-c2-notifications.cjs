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
  "components/core/NotificationManagementView.tsx",
  "components/app/AppShell.tsx",
  "lib/notification-management.ts",
  "lib/core-types.ts",
  "lib/navigation.ts",
  "app/page.tsx",
  "app/api/core/notifications/route.ts",
  "app/api/core/notifications/unread-count/route.ts",
  "app/api/core/notifications/read-all/route.ts",
  "app/api/core/notifications/[notificationId]/read/route.ts",
  "app/api/core/notifications/[notificationId]/unread/route.ts",
];
for (const target of compileTargets) compile(target);

const nav = read("lib/navigation.ts");
const shell = read("components/app/AppShell.tsx");
const page = read("app/page.tsx");
const component = read("components/core/NotificationManagementView.tsx");
const css = read("app/globals.css");

ok(/key: "notifications"/.test(nav), "notifications navigation item missing");
ok(!/key: "notifications"[\s\S]*requiredAny/.test(nav.split('key: "notifications"')[1]?.split('key: "access"')[0] ?? ""), "personal notifications must not require a B3 organization permission");
ok(/notificationUnreadCount/.test(shell), "topbar unread count is not wired");
ok(/navigate\("notifications"\)/.test(shell), "notification bell does not open notifications view");
ok(/NotificationManagementView/.test(page), "notifications view is not mounted");
ok(/api\/core\/notifications\/unread-count/.test(page), "shell unread count is not fetched");
ok(/api\/core\/notifications\/read-all/.test(component), "mark-all-read is not wired");
ok(/encodeURIComponent\(item\.id\)/.test(component), "dynamic notification IDs are not encoded in the UI");
ok(/window\.location\.assign\(item\.action_path\)/.test(component), "local notification action is not wired");
ok(/\.notification-bell/.test(css), "notification bell styling missing");
ok(/\.notification-card\.is-unread/.test(css), "unread notification styling missing");

const writeRoutes = [
  "app/api/core/notifications/read-all/route.ts",
  "app/api/core/notifications/[notificationId]/read/route.ts",
  "app/api/core/notifications/[notificationId]/unread/route.ts",
];
for (const route of writeRoutes) {
  ok(/proxyAuthenticatedRequest/.test(read(route)), `${route} bypasses centralized mutation proxy`);
}
for (const route of writeRoutes.filter((item) => item.includes("["))) {
  ok(/encodeURIComponent\(notificationId\)/.test(read(route)), `${route} does not encode dynamic notification ID`);
}
ok(/proxyAuthenticatedGet/.test(read("app/api/core/notifications/route.ts")), "notification list bypasses authenticated BFF");
ok(/proxyAuthenticatedGet/.test(read("app/api/core/notifications/unread-count/route.ts")), "unread count bypasses authenticated BFF");

console.log(`C2 notification UI checks passed (${assertions} assertions).`);
