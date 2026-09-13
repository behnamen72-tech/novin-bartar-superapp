import type {
  WorkflowDefinitionItem,
  WorkflowInstanceItem,
  WorkflowOrganizationCapability,
  WorkflowStateItem,
  WorkflowTransitionItem,
} from "@/lib/core-types";

export const workflowDefinitionStatusLabels = {
  draft: "پیش‌نویس",
  published: "منتشرشده",
  retired: "بازنشسته",
} as const;

export const workflowInstanceStatusLabels = {
  active: "در حال اجرا",
  completed: "تکمیل‌شده",
  cancelled: "لغوشده",
} as const;

export function workflowScopeLabel(scope: "self" | "self_and_descendants"): string {
  return scope === "self_and_descendants" ? "سازمان + زیرمجموعه‌ها" : "فقط همان سازمان";
}

export function stateById(
  definition: WorkflowDefinitionItem | undefined,
  stateId: string,
): WorkflowStateItem | undefined {
  return definition?.states.find((state) => state.id === stateId);
}

export function availableTransitions(
  definition: WorkflowDefinitionItem | undefined,
  instance: WorkflowInstanceItem,
): WorkflowTransitionItem[] {
  if (!definition || instance.status !== "active") return [];
  return definition.transitions.filter(
    (transition) => transition.from_state_id === instance.current_state_id,
  );
}

export function workflowCapabilitySummary(
  organization: WorkflowOrganizationCapability,
): string[] {
  const labels: string[] = [];
  if (organization.can_read) labels.push("مشاهده");
  if (organization.can_manage) labels.push("طراحی");
  if (organization.can_execute) labels.push("اجرا");
  return labels;
}

export function sortWorkflowDefinitions(
  definitions: readonly WorkflowDefinitionItem[],
): WorkflowDefinitionItem[] {
  return [...definitions].sort((a, b) => {
    const codeCompare = a.code.localeCompare(b.code, "en");
    if (codeCompare !== 0) return codeCompare;
    return b.version - a.version;
  });
}

export function sortWorkflowStates(states: readonly WorkflowStateItem[]): WorkflowStateItem[] {
  return [...states].sort((a, b) => {
    if (a.position !== b.position) return a.position - b.position;
    return a.code.localeCompare(b.code, "en");
  });
}

export function normalizeWorkflowCode(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "-");
}
