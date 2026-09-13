"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { AppNotice } from "@/components/ui/AppNotice";
import { AsyncState } from "@/components/ui/AsyncState";
import { ApiError, apiFetch } from "@/lib/api-client";
import type {
  ScopeMode,
  WorkflowDefinitionItem,
  WorkflowInstanceItem,
  WorkflowOrganizationCapability,
  WorkflowStateItem,
  WorkflowTransitionItem,
} from "@/lib/core-types";
import {
  availableTransitions,
  normalizeWorkflowCode,
  sortWorkflowDefinitions,
  sortWorkflowStates,
  stateById,
  workflowCapabilitySummary,
  workflowDefinitionStatusLabels,
  workflowInstanceStatusLabels,
  workflowScopeLabel,
} from "@/lib/workflow-management";

type Tab = "definitions" | "instances";
type DefinitionEditor =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; definition: WorkflowDefinitionItem };
type StateEditor =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; state: WorkflowStateItem };
type TransitionEditor =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; transition: WorkflowTransitionItem };

function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "عملیات انجام نشد. ارتباط با Backend را بررسی کنید.";
  }
  const known: Record<string, string> = {
    "Permission denied.": "برای این عملیات مجوز کافی ندارید.",
    "Workflow definition not found.": "گردش‌کار پیدا نشد یا در محدوده دسترسی شما نیست.",
    "Workflow instance not found.": "نمونه گردش‌کار پیدا نشد یا در محدوده دسترسی شما نیست.",
    "A published workflow must have exactly one initial state.":
      "برای انتشار باید دقیقاً یک مرحله آغازین تعریف شود.",
    "A published workflow must have at least one terminal state.":
      "برای انتشار باید حداقل یک مرحله پایانی تعریف شود.",
    "Every non-terminal state must have at least one outgoing transition.":
      "هر مرحله غیرپایانی باید حداقل یک مسیر خروجی داشته باشد.",
    "Every workflow state must be reachable from the initial state.":
      "همه مراحل باید از مرحله آغازین قابل دسترسی باشند.",
    "Published or retired workflow definitions are immutable; create a new version instead.":
      "نسخه منتشرشده یا بازنشسته قابل ویرایش نیست؛ نسخه جدید بسازید.",
    "This resource already has an instance for this workflow version.":
      "برای این منبع و این نسخه گردش‌کار قبلاً یک نمونه ساخته شده است.",
    "Only active workflow instances can transition.":
      "فقط گردش‌کارهای در حال اجرا قابل انتقال به مرحله بعد هستند.",
    "Completed workflow instances cannot be cancelled.":
      "گردش‌کار تکمیل‌شده قابل لغو نیست.",
    "Transition is not available from the current state.":
      "این انتقال از مرحله فعلی در دسترس نیست.",
  };
  return known[error.detail] ?? error.detail ?? "عملیات انجام نشد.";
}

function statusClass(status: string): string {
  if (status === "published" || status === "completed") return "is-success";
  if (status === "retired" || status === "cancelled") return "is-muted";
  return "is-warning";
}

export function WorkflowManagementView() {
  const [tab, setTab] = useState<Tab>("definitions");
  const [organizations, setOrganizations] = useState<WorkflowOrganizationCapability[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [definitions, setDefinitions] = useState<WorkflowDefinitionItem[]>([]);
  const [instances, setInstances] = useState<WorkflowInstanceItem[]>([]);
  const [selectedDefinitionId, setSelectedDefinitionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  const [definitionEditor, setDefinitionEditor] = useState<DefinitionEditor>({ mode: "closed" });
  const [definitionName, setDefinitionName] = useState("");
  const [definitionCode, setDefinitionCode] = useState("");
  const [definitionDescription, setDefinitionDescription] = useState("");
  const [definitionScope, setDefinitionScope] = useState<ScopeMode>("self");

  const [stateEditor, setStateEditor] = useState<StateEditor>({ mode: "closed" });
  const [stateCode, setStateCode] = useState("");
  const [stateName, setStateName] = useState("");
  const [statePosition, setStatePosition] = useState("0");
  const [stateInitial, setStateInitial] = useState(false);
  const [stateTerminal, setStateTerminal] = useState(false);

  const [transitionEditor, setTransitionEditor] = useState<TransitionEditor>({ mode: "closed" });
  const [transitionCode, setTransitionCode] = useState("");
  const [transitionName, setTransitionName] = useState("");
  const [transitionFrom, setTransitionFrom] = useState("");
  const [transitionTo, setTransitionTo] = useState("");

  const [startOpen, setStartOpen] = useState(false);
  const [startDefinitionId, setStartDefinitionId] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [instanceStatusFilter, setInstanceStatusFilter] = useState<"all" | "active" | "completed" | "cancelled">("all");

  const selectedOrganization = useMemo(
    () => organizations.find((item) => item.id === organizationId),
    [organizationId, organizations],
  );
  const selectedDefinition = useMemo(
    () => definitions.find((item) => item.id === selectedDefinitionId),
    [definitions, selectedDefinitionId],
  );
  const definitionsById = useMemo(
    () => new Map(definitions.map((definition) => [definition.id, definition])),
    [definitions],
  );
  const publishedDefinitions = useMemo(
    () => definitions.filter((definition) => definition.status === "published"),
    [definitions],
  );
  const filteredInstances = useMemo(
    () =>
      instanceStatusFilter === "all"
        ? instances
        : instances.filter((item) => item.status === instanceStatusFilter),
    [instanceStatusFilter, instances],
  );

  const loadOrganizations = useCallback(async () => {
    setLoading(true);
    setNotice(null);
    try {
      const items = await apiFetch<WorkflowOrganizationCapability[]>("/api/core/workflow/organizations");
      setOrganizations(items);
      setOrganizationId((current) => {
        if (current && items.some((item) => item.id === current)) return current;
        return items.find((item) => item.can_read)?.id ?? items[0]?.id ?? "";
      });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  const loadOrganizationData = useCallback(async (targetId: string) => {
    const capability = organizations.find((item) => item.id === targetId);
    if (!capability) return;
    setRefreshing(true);
    setNotice(null);
    try {
      const nextDefinitions = capability.can_read
        ? await apiFetch<WorkflowDefinitionItem[]>(
            `/api/core/workflow/definitions?organization_id=${encodeURIComponent(targetId)}&include_drafts=${capability.can_manage ? "true" : "false"}`,
          )
        : [];
      setDefinitions(sortWorkflowDefinitions(nextDefinitions));
      setSelectedDefinitionId((current) =>
        current && nextDefinitions.some((item) => item.id === current)
          ? current
          : nextDefinitions[0]?.id ?? null,
      );
      const nextInstances = capability.can_read
        ? await apiFetch<WorkflowInstanceItem[]>(
            `/api/core/workflow/instances?organization_id=${encodeURIComponent(targetId)}&limit=200`,
          )
        : [];
      setInstances(nextInstances);
    } catch (error) {
      setDefinitions([]);
      setInstances([]);
      setSelectedDefinitionId(null);
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setRefreshing(false);
    }
  }, [organizations]);

  useEffect(() => {
    void loadOrganizations();
  }, [loadOrganizations]);

  useEffect(() => {
    if (organizationId) void loadOrganizationData(organizationId);
  }, [loadOrganizationData, organizationId]);

  function replaceDefinition(updated: WorkflowDefinitionItem) {
    setDefinitions((current) => {
      const exists = current.some((item) => item.id === updated.id);
      return sortWorkflowDefinitions(
        exists ? current.map((item) => (item.id === updated.id ? updated : item)) : [...current, updated],
      );
    });
    setSelectedDefinitionId(updated.id);
  }

  function replaceInstance(updated: WorkflowInstanceItem) {
    setInstances((current) => {
      const exists = current.some((item) => item.id === updated.id);
      return exists ? current.map((item) => (item.id === updated.id ? updated : item)) : [updated, ...current];
    });
  }

  function openCreateDefinition() {
    setDefinitionName("");
    setDefinitionCode("");
    setDefinitionDescription("");
    setDefinitionScope("self");
    setDefinitionEditor({ mode: "create" });
  }

  function openEditDefinition(definition: WorkflowDefinitionItem) {
    setDefinitionName(definition.name);
    setDefinitionCode(definition.code);
    setDefinitionDescription(definition.description ?? "");
    setDefinitionScope(definition.scope_mode);
    setDefinitionEditor({ mode: "edit", definition });
  }

  async function submitDefinition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganization) return;
    setBusy(true);
    setNotice(null);
    try {
      if (definitionEditor.mode === "create") {
        const created = await apiFetch<WorkflowDefinitionItem>("/api/core/workflow/definitions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            organization_id: selectedOrganization.id,
            code: normalizeWorkflowCode(definitionCode),
            name: definitionName.trim(),
            description: definitionDescription.trim() || null,
            scope_mode: definitionScope,
          }),
        });
        replaceDefinition(created);
        setNotice({ tone: "success", text: "گردش‌کار جدید به‌صورت پیش‌نویس ساخته شد." });
      } else if (definitionEditor.mode === "edit") {
        const updated = await apiFetch<WorkflowDefinitionItem>(
          `/api/core/workflow/definitions/${encodeURIComponent(definitionEditor.definition.id)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: definitionName.trim(),
              description: definitionDescription.trim() || null,
              scope_mode: definitionScope,
            }),
          },
        );
        replaceDefinition(updated);
        setNotice({ tone: "success", text: "مشخصات گردش‌کار به‌روزرسانی شد." });
      }
      setDefinitionEditor({ mode: "closed" });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  }

  function openCreateState() {
    setStateCode("");
    setStateName("");
    setStatePosition(String(selectedDefinition?.states.length ?? 0));
    setStateInitial((selectedDefinition?.states.length ?? 0) === 0);
    setStateTerminal(false);
    setStateEditor({ mode: "create" });
  }

  function openEditState(state: WorkflowStateItem) {
    setStateCode(state.code);
    setStateName(state.name);
    setStatePosition(String(state.position));
    setStateInitial(state.is_initial);
    setStateTerminal(state.is_terminal);
    setStateEditor({ mode: "edit", state });
  }

  async function submitState(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDefinition) return;
    setBusy(true);
    setNotice(null);
    try {
      const base = `/api/core/workflow/definitions/${encodeURIComponent(selectedDefinition.id)}/states`;
      const updated = await apiFetch<WorkflowDefinitionItem>(
        stateEditor.mode === "edit" ? `${base}/${encodeURIComponent(stateEditor.state.id)}` : base,
        {
          method: stateEditor.mode === "edit" ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            stateEditor.mode === "edit"
              ? {
                  name: stateName.trim(),
                  position: Number(statePosition),
                  is_initial: stateInitial,
                  is_terminal: stateTerminal,
                }
              : {
                  code: normalizeWorkflowCode(stateCode),
                  name: stateName.trim(),
                  position: Number(statePosition),
                  is_initial: stateInitial,
                  is_terminal: stateTerminal,
                },
          ),
        },
      );
      replaceDefinition(updated);
      setStateEditor({ mode: "closed" });
      setNotice({ tone: "success", text: "مرحله گردش‌کار ذخیره شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  }

  async function deleteState(state: WorkflowStateItem) {
    if (!selectedDefinition || !window.confirm(`مرحله «${state.name}» حذف شود؟`)) return;
    setBusy(true);
    setNotice(null);
    try {
      const updated = await apiFetch<WorkflowDefinitionItem>(
        `/api/core/workflow/definitions/${encodeURIComponent(selectedDefinition.id)}/states/${encodeURIComponent(state.id)}`,
        { method: "DELETE" },
      );
      replaceDefinition(updated);
      setNotice({ tone: "success", text: "مرحله حذف شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  }

  function openCreateTransition() {
    const states = sortWorkflowStates(selectedDefinition?.states ?? []);
    setTransitionCode("");
    setTransitionName("");
    setTransitionFrom(states.find((state) => !state.is_terminal)?.id ?? states[0]?.id ?? "");
    setTransitionTo(states[1]?.id ?? states[0]?.id ?? "");
    setTransitionEditor({ mode: "create" });
  }

  function openEditTransition(transition: WorkflowTransitionItem) {
    setTransitionCode(transition.code);
    setTransitionName(transition.name);
    setTransitionFrom(transition.from_state_id);
    setTransitionTo(transition.to_state_id);
    setTransitionEditor({ mode: "edit", transition });
  }

  async function submitTransition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDefinition) return;
    setBusy(true);
    setNotice(null);
    try {
      const base = `/api/core/workflow/definitions/${encodeURIComponent(selectedDefinition.id)}/transitions`;
      const updated = await apiFetch<WorkflowDefinitionItem>(
        transitionEditor.mode === "edit"
          ? `${base}/${encodeURIComponent(transitionEditor.transition.id)}`
          : base,
        {
          method: transitionEditor.mode === "edit" ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            transitionEditor.mode === "edit"
              ? {
                  name: transitionName.trim(),
                  from_state_id: transitionFrom,
                  to_state_id: transitionTo,
                }
              : {
                  code: normalizeWorkflowCode(transitionCode),
                  name: transitionName.trim(),
                  from_state_id: transitionFrom,
                  to_state_id: transitionTo,
                },
          ),
        },
      );
      replaceDefinition(updated);
      setTransitionEditor({ mode: "closed" });
      setNotice({ tone: "success", text: "مسیر انتقال ذخیره شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  }

  async function deleteTransition(transition: WorkflowTransitionItem) {
    if (!selectedDefinition || !window.confirm(`مسیر «${transition.name}» حذف شود؟`)) return;
    setBusy(true);
    setNotice(null);
    try {
      const updated = await apiFetch<WorkflowDefinitionItem>(
        `/api/core/workflow/definitions/${encodeURIComponent(selectedDefinition.id)}/transitions/${encodeURIComponent(transition.id)}`,
        { method: "DELETE" },
      );
      replaceDefinition(updated);
      setNotice({ tone: "success", text: "مسیر انتقال حذف شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  }

  async function definitionAction(action: "publish" | "retire" | "new-version") {
    if (!selectedDefinition) return;
    const prompts = {
      publish: "این نسخه منتشر شود؟ بعد از انتشار دیگر قابل ویرایش مستقیم نیست.",
      retire: "این نسخه بازنشسته شود؟ نمونه‌های موجود همچنان تاریخچه خود را حفظ می‌کنند.",
      "new-version": "از این گردش‌کار یک نسخه پیش‌نویس جدید ساخته شود؟",
    };
    if (!window.confirm(prompts[action])) return;
    setBusy(true);
    setNotice(null);
    try {
      const updated = await apiFetch<WorkflowDefinitionItem>(
        `/api/core/workflow/definitions/${encodeURIComponent(selectedDefinition.id)}/${action}`,
        { method: "POST" },
      );
      if (action === "publish") {
        await loadOrganizationData(organizationId);
        setSelectedDefinitionId(updated.id);
      } else {
        replaceDefinition(updated);
      }
      setNotice({
        tone: "success",
        text:
          action === "publish"
            ? "نسخه گردش‌کار منتشر شد."
            : action === "retire"
              ? "نسخه گردش‌کار بازنشسته شد."
              : "نسخه پیش‌نویس جدید ساخته شد.",
      });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  }

  async function startInstance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedOrganization) return;
    setBusy(true);
    setNotice(null);
    try {
      const created = await apiFetch<WorkflowInstanceItem>("/api/core/workflow/instances", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          definition_id: startDefinitionId,
          organization_id: selectedOrganization.id,
          resource_type: resourceType.trim().toLowerCase(),
          resource_id: resourceId.trim(),
        }),
      });
      replaceInstance(created);
      setStartOpen(false);
      setResourceType("");
      setResourceId("");
      setNotice({ tone: "success", text: "نمونه گردش‌کار شروع شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  }

  async function runTransition(instance: WorkflowInstanceItem, transition: WorkflowTransitionItem) {
    const comment = window.prompt(`انتقال «${transition.name}» انجام شود؟ توضیح اختیاری:`, "");
    if (comment === null) return;
    setBusy(true);
    setNotice(null);
    try {
      const updated = await apiFetch<WorkflowInstanceItem>(
        `/api/core/workflow/instances/${encodeURIComponent(instance.id)}/transition`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ transition_id: transition.id, comment: comment.trim() || null }),
        },
      );
      replaceInstance(updated);
      setNotice({ tone: "success", text: `گردش‌کار با مسیر «${transition.name}» جلو رفت.` });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  }

  async function cancelInstance(instance: WorkflowInstanceItem) {
    if (!window.confirm("این نمونه گردش‌کار لغو شود؟")) return;
    setBusy(true);
    setNotice(null);
    try {
      const updated = await apiFetch<WorkflowInstanceItem>(
        `/api/core/workflow/instances/${encodeURIComponent(instance.id)}/cancel`,
        { method: "POST" },
      );
      replaceInstance(updated);
      setNotice({ tone: "success", text: "گردش‌کار لغو شد." });
    } catch (error) {
      setNotice({ tone: "error", text: errorMessage(error) });
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <AsyncState label="در حال بارگذاری مرکز گردش‌کار…" />;
  }

  return (
    <section className="page-section workflow-management">
      <div className="management-page-title workflow-title-actions">
        <div>
          <span>Workflow Core</span>
          <h1>گردش‌کارها</h1>
          <p>
            تعریف مراحل، انتشار نسخه‌ها و اجرای فرآیندها روی منابع مختلف؛ تمام کنترل‌های امنیتی دوباره در Backend اعمال می‌شوند.
          </p>
        </div>
        <div className="workflow-title-controls">
          <select
            aria-label="سازمان گردش‌کار"
            value={organizationId}
            onChange={(event) => setOrganizationId(event.target.value)}
            disabled={refreshing || busy}
          >
            {organizations.map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name} — {workflowCapabilitySummary(organization).join(" / ")}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="secondary-action-button"
            disabled={!organizationId || refreshing || busy}
            onClick={() => void loadOrganizationData(organizationId)}
          >
            {refreshing ? "در حال تازه‌سازی…" : "تازه‌سازی"}
          </button>
        </div>
      </div>

      {notice ? <AppNotice tone={notice.tone}>{notice.text}</AppNotice> : null}

      {organizations.length === 0 ? (
        <div className="empty-state">هیچ محدوده سازمانی با مجوز Workflow برای این کاربر وجود ندارد.</div>
      ) : null}

      {selectedOrganization ? (
        <div className="workflow-capability-strip">
          <span>{selectedOrganization.name}</span>
          <b>{workflowCapabilitySummary(selectedOrganization).join(" • ")}</b>
          {!selectedOrganization.can_read ? (
            <small>برای فهرست‌کردن گردش‌کارها و نمونه‌ها، مجوز workflow.read لازم است.</small>
          ) : null}
        </div>
      ) : null}

      <div className="workflow-tabs" role="tablist" aria-label="بخش‌های گردش‌کار">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "definitions"}
          className={tab === "definitions" ? "active" : ""}
          onClick={() => setTab("definitions")}
        >
          طراحی گردش‌کار
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "instances"}
          className={tab === "instances" ? "active" : ""}
          onClick={() => setTab("instances")}
        >
          اجرا و پیگیری
        </button>
      </div>

      {tab === "definitions" ? (
        <div className="workflow-definitions-layout">
          <aside className="workflow-definition-list">
            <div className="workflow-panel-head">
              <div>
                <strong>تعریف‌ها و نسخه‌ها</strong>
                <small>{definitions.length.toLocaleString("fa-IR")} نسخه قابل مشاهده</small>
              </div>
              {selectedOrganization?.can_manage ? (
                <button type="button" className="primary-action-button" onClick={openCreateDefinition} disabled={busy}>
                  تعریف جدید
                </button>
              ) : null}
            </div>
            {definitions.map((definition) => (
              <button
                type="button"
                key={definition.id}
                className={`workflow-definition-card ${selectedDefinitionId === definition.id ? "active" : ""}`}
                onClick={() => setSelectedDefinitionId(definition.id)}
              >
                <div>
                  <strong>{definition.name}</strong>
                  <span dir="ltr">{definition.code} · v{definition.version}</span>
                </div>
                <span className={`workflow-status ${statusClass(definition.status)}`}>
                  {workflowDefinitionStatusLabels[definition.status]}
                </span>
                <small>{workflowScopeLabel(definition.scope_mode)}</small>
              </button>
            ))}
            {definitions.length === 0 ? (
              <div className="empty-state compact">گردش‌کاری برای این سازمان قابل مشاهده نیست.</div>
            ) : null}
          </aside>

          <div className="workflow-definition-detail">
            {selectedDefinition ? (
              <>
                <div className="workflow-detail-head">
                  <div>
                    <span>نسخه {selectedDefinition.version.toLocaleString("fa-IR")}</span>
                    <h2>{selectedDefinition.name}</h2>
                    <p>{selectedDefinition.description ?? "بدون توضیح"}</p>
                  </div>
                  <div className="workflow-detail-actions">
                    {selectedDefinition.status === "draft" && selectedOrganization?.can_manage ? (
                      <>
                        <button type="button" className="secondary-action-button" onClick={() => openEditDefinition(selectedDefinition)} disabled={busy}>
                          ویرایش مشخصات
                        </button>
                        <button type="button" className="primary-action-button" onClick={() => void definitionAction("publish")} disabled={busy}>
                          انتشار نسخه
                        </button>
                      </>
                    ) : null}
                    {selectedDefinition.status === "published" && selectedOrganization?.can_manage ? (
                      <>
                        <button type="button" className="secondary-action-button" onClick={() => void definitionAction("new-version")} disabled={busy}>
                          نسخه جدید
                        </button>
                        <button type="button" className="status-action-button danger" onClick={() => void definitionAction("retire")} disabled={busy}>
                          بازنشسته‌کردن
                        </button>
                      </>
                    ) : null}
                    {selectedDefinition.status === "retired" && selectedOrganization?.can_manage ? (
                      <button type="button" className="secondary-action-button" onClick={() => void definitionAction("new-version")} disabled={busy}>
                        نسخه جدید
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className="workflow-definition-meta">
                  <span>کد <b dir="ltr">{selectedDefinition.code}</b></span>
                  <span>Scope <b>{workflowScopeLabel(selectedDefinition.scope_mode)}</b></span>
                  <span>مرحله <b>{selectedDefinition.states.length.toLocaleString("fa-IR")}</b></span>
                  <span>مسیر <b>{selectedDefinition.transitions.length.toLocaleString("fa-IR")}</b></span>
                </div>

                <div className="workflow-builder-columns">
                  <div className="workflow-builder-panel">
                    <div className="workflow-panel-head">
                      <div>
                        <strong>مراحل</strong>
                        <small>یک مرحله آغازین و حداقل یک مرحله پایانی لازم است.</small>
                      </div>
                      {selectedDefinition.status === "draft" && selectedOrganization?.can_manage ? (
                        <button type="button" className="secondary-action-button" onClick={openCreateState} disabled={busy}>
                          + مرحله
                        </button>
                      ) : null}
                    </div>
                    <div className="workflow-state-list">
                      {sortWorkflowStates(selectedDefinition.states).map((state) => (
                        <article className="workflow-state-row" key={state.id}>
                          <div className="workflow-state-index">{state.position.toLocaleString("fa-IR")}</div>
                          <div>
                            <strong>{state.name}</strong>
                            <span dir="ltr">{state.code}</span>
                          </div>
                          <div className="workflow-state-flags">
                            {state.is_initial ? <span>آغاز</span> : null}
                            {state.is_terminal ? <span>پایان</span> : null}
                          </div>
                          {selectedDefinition.status === "draft" && selectedOrganization?.can_manage ? (
                            <div className="workflow-inline-actions">
                              <button type="button" onClick={() => openEditState(state)} disabled={busy}>ویرایش</button>
                              <button type="button" className="danger-text" onClick={() => void deleteState(state)} disabled={busy}>حذف</button>
                            </div>
                          ) : null}
                        </article>
                      ))}
                      {selectedDefinition.states.length === 0 ? <div className="empty-state compact">هنوز مرحله‌ای تعریف نشده است.</div> : null}
                    </div>
                  </div>

                  <div className="workflow-builder-panel">
                    <div className="workflow-panel-head">
                      <div>
                        <strong>مسیرهای انتقال</strong>
                        <small>مسیرها مشخص می‌کنند هر مرحله به کجا می‌تواند برود.</small>
                      </div>
                      {selectedDefinition.status === "draft" && selectedOrganization?.can_manage && selectedDefinition.states.length >= 2 ? (
                        <button type="button" className="secondary-action-button" onClick={openCreateTransition} disabled={busy}>
                          + مسیر
                        </button>
                      ) : null}
                    </div>
                    <div className="workflow-transition-list">
                      {selectedDefinition.transitions.map((transition) => (
                        <article className="workflow-transition-row" key={transition.id}>
                          <div>
                            <strong>{transition.name}</strong>
                            <span dir="ltr">{transition.code}</span>
                          </div>
                          <div className="workflow-transition-flow">
                            <span>{stateById(selectedDefinition, transition.from_state_id)?.name ?? "؟"}</span>
                            <b>←</b>
                            <span>{stateById(selectedDefinition, transition.to_state_id)?.name ?? "؟"}</span>
                          </div>
                          {selectedDefinition.status === "draft" && selectedOrganization?.can_manage ? (
                            <div className="workflow-inline-actions">
                              <button type="button" onClick={() => openEditTransition(transition)} disabled={busy}>ویرایش</button>
                              <button type="button" className="danger-text" onClick={() => void deleteTransition(transition)} disabled={busy}>حذف</button>
                            </div>
                          ) : null}
                        </article>
                      ))}
                      {selectedDefinition.transitions.length === 0 ? <div className="empty-state compact">هنوز مسیر انتقالی تعریف نشده است.</div> : null}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="empty-state">یک گردش‌کار را از فهرست انتخاب کنید.</div>
            )}
          </div>
        </div>
      ) : (
        <div className="workflow-instances-panel">
          <div className="workflow-panel-head workflow-instance-toolbar">
            <div>
              <strong>نمونه‌های در حال اجرا و تاریخچه</strong>
              <small>هر نمونه یک گردش‌کار مشخص را روی یک منبع مشخص دنبال می‌کند.</small>
            </div>
            <div className="workflow-instance-toolbar-actions">
              <select value={instanceStatusFilter} onChange={(event) => setInstanceStatusFilter(event.target.value as typeof instanceStatusFilter)}>
                <option value="all">همه وضعیت‌ها</option>
                <option value="active">در حال اجرا</option>
                <option value="completed">تکمیل‌شده</option>
                <option value="cancelled">لغوشده</option>
              </select>
              {selectedOrganization?.can_execute && publishedDefinitions.length > 0 ? (
                <button
                  type="button"
                  className="primary-action-button"
                  onClick={() => {
                    setStartDefinitionId(publishedDefinitions[0]?.id ?? "");
                    setStartOpen(true);
                  }}
                  disabled={busy}
                >
                  شروع گردش‌کار
                </button>
              ) : null}
            </div>
          </div>

          <div className="workflow-instance-list">
            {filteredInstances.map((instance) => {
              const definition = definitionsById.get(instance.definition_id);
              const currentState = stateById(definition, instance.current_state_id);
              const transitions = availableTransitions(definition, instance);
              return (
                <article className="workflow-instance-card" key={instance.id}>
                  <div className="workflow-instance-head">
                    <div>
                      <span>{definition?.name ?? "گردش‌کار"}</span>
                      <strong>{instance.resource_type} / {instance.resource_id}</strong>
                      <small dir="ltr">{instance.id}</small>
                    </div>
                    <span className={`workflow-status ${statusClass(instance.status)}`}>
                      {workflowInstanceStatusLabels[instance.status]}
                    </span>
                  </div>
                  <div className="workflow-instance-current">
                    <span>مرحله فعلی</span>
                    <strong>{currentState?.name ?? instance.current_state_id}</strong>
                  </div>
                  {instance.status === "active" && selectedOrganization?.can_execute ? (
                    <div className="workflow-instance-actions">
                      {transitions.map((transition) => (
                        <button key={transition.id} type="button" className="primary-action-button" disabled={busy} onClick={() => void runTransition(instance, transition)}>
                          {transition.name}
                        </button>
                      ))}
                      <button type="button" className="status-action-button danger" disabled={busy} onClick={() => void cancelInstance(instance)}>
                        لغو گردش‌کار
                      </button>
                    </div>
                  ) : null}
                  <details className="workflow-history">
                    <summary>تاریخچه انتقال‌ها ({instance.history.length.toLocaleString("fa-IR")})</summary>
                    <div>
                      {instance.history.map((record) => (
                        <article key={record.id}>
                          <strong>
                            {stateById(definition, record.from_state_id)?.name ?? "؟"} ← {stateById(definition, record.to_state_id)?.name ?? "؟"}
                          </strong>
                          <span>{new Date(record.occurred_at).toLocaleString("fa-IR")}</span>
                          <small>{record.comment ?? "بدون توضیح"}</small>
                        </article>
                      ))}
                      {instance.history.length === 0 ? <span>هنوز انتقالی ثبت نشده است.</span> : null}
                    </div>
                  </details>
                </article>
              );
            })}
            {filteredInstances.length === 0 ? <div className="empty-state">نمونه‌ای با این فیلتر وجود ندارد.</div> : null}
          </div>
        </div>
      )}

      {definitionEditor.mode !== "closed" ? (
        <Dialog title={definitionEditor.mode === "create" ? "تعریف گردش‌کار جدید" : "ویرایش گردش‌کار"} onClose={() => !busy && setDefinitionEditor({ mode: "closed" })}>
          <form className="management-form" onSubmit={submitDefinition}>
            <label><span>نام</span><input value={definitionName} onChange={(event) => setDefinitionName(event.target.value)} required maxLength={180} /></label>
            {definitionEditor.mode === "create" ? (
              <label><span>کد</span><input dir="ltr" value={definitionCode} onChange={(event) => setDefinitionCode(event.target.value)} required maxLength={100} placeholder="purchase-approval" /></label>
            ) : null}
            <label><span>توضیح</span><textarea value={definitionDescription} onChange={(event) => setDefinitionDescription(event.target.value)} maxLength={1000} rows={3} /></label>
            <label><span>محدوده اجرا</span><select value={definitionScope} onChange={(event) => setDefinitionScope(event.target.value as ScopeMode)}><option value="self">فقط همان سازمان</option><option value="self_and_descendants">سازمان + زیرمجموعه‌ها</option></select></label>
            <div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setDefinitionEditor({ mode: "closed" })} disabled={busy}>انصراف</button><button type="submit" className="primary-action-button" disabled={busy}>{busy ? "در حال ذخیره…" : "ذخیره"}</button></div>
          </form>
        </Dialog>
      ) : null}

      {stateEditor.mode !== "closed" ? (
        <Dialog title={stateEditor.mode === "create" ? "مرحله جدید" : "ویرایش مرحله"} onClose={() => !busy && setStateEditor({ mode: "closed" })}>
          <form className="management-form" onSubmit={submitState}>
            <label><span>نام مرحله</span><input value={stateName} onChange={(event) => setStateName(event.target.value)} required maxLength={180} /></label>
            {stateEditor.mode === "create" ? <label><span>کد مرحله</span><input dir="ltr" value={stateCode} onChange={(event) => setStateCode(event.target.value)} required maxLength={100} placeholder="manager-review" /></label> : null}
            <label><span>ترتیب نمایش</span><input type="number" min="0" value={statePosition} onChange={(event) => setStatePosition(event.target.value)} required /></label>
            <label className="workflow-checkbox"><input type="checkbox" checked={stateInitial} onChange={(event) => setStateInitial(event.target.checked)} /><span>مرحله آغازین</span></label>
            <label className="workflow-checkbox"><input type="checkbox" checked={stateTerminal} onChange={(event) => setStateTerminal(event.target.checked)} /><span>مرحله پایانی</span></label>
            <div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setStateEditor({ mode: "closed" })} disabled={busy}>انصراف</button><button type="submit" className="primary-action-button" disabled={busy}>ذخیره مرحله</button></div>
          </form>
        </Dialog>
      ) : null}

      {transitionEditor.mode !== "closed" && selectedDefinition ? (
        <Dialog title={transitionEditor.mode === "create" ? "مسیر انتقال جدید" : "ویرایش مسیر انتقال"} onClose={() => !busy && setTransitionEditor({ mode: "closed" })}>
          <form className="management-form" onSubmit={submitTransition}>
            <label><span>نام مسیر</span><input value={transitionName} onChange={(event) => setTransitionName(event.target.value)} required maxLength={180} /></label>
            {transitionEditor.mode === "create" ? <label><span>کد مسیر</span><input dir="ltr" value={transitionCode} onChange={(event) => setTransitionCode(event.target.value)} required maxLength={100} placeholder="approve" /></label> : null}
            <label><span>از مرحله</span><select value={transitionFrom} onChange={(event) => setTransitionFrom(event.target.value)} required>{sortWorkflowStates(selectedDefinition.states).map((state) => <option key={state.id} value={state.id} disabled={state.is_terminal}>{state.name}{state.is_terminal ? " (پایانی)" : ""}</option>)}</select></label>
            <label><span>به مرحله</span><select value={transitionTo} onChange={(event) => setTransitionTo(event.target.value)} required>{sortWorkflowStates(selectedDefinition.states).map((state) => <option key={state.id} value={state.id}>{state.name}</option>)}</select></label>
            <div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setTransitionEditor({ mode: "closed" })} disabled={busy}>انصراف</button><button type="submit" className="primary-action-button" disabled={busy}>ذخیره مسیر</button></div>
          </form>
        </Dialog>
      ) : null}

      {startOpen ? (
        <Dialog title="شروع یک گردش‌کار" onClose={() => !busy && setStartOpen(false)}>
          <form className="management-form" onSubmit={startInstance}>
            <label><span>گردش‌کار منتشرشده</span><select value={startDefinitionId} onChange={(event) => setStartDefinitionId(event.target.value)} required>{publishedDefinitions.map((definition) => <option key={definition.id} value={definition.id}>{definition.name} — v{definition.version}</option>)}</select></label>
            <label><span>نوع منبع</span><input dir="ltr" value={resourceType} onChange={(event) => setResourceType(event.target.value)} required maxLength={100} placeholder="purchase_request" /></label>
            <label><span>شناسه منبع</span><input dir="ltr" value={resourceId} onChange={(event) => setResourceId(event.target.value)} required maxLength={160} placeholder="PR-1405-001" /></label>
            <div className="management-form-note">در فازهای تجاری بعدی، فرم‌های خرید، قرارداد، منابع انسانی و عملیات این شناسه‌ها را خودکار به Workflow متصل می‌کنند.</div>
            <div className="management-form-actions"><button type="button" className="secondary-action-button" onClick={() => setStartOpen(false)} disabled={busy}>انصراف</button><button type="submit" className="primary-action-button" disabled={busy || !startDefinitionId}>شروع</button></div>
          </form>
        </Dialog>
      ) : null}
    </section>
  );
}

function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="management-dialog-layer" role="presentation">
      <button type="button" className="management-dialog-backdrop" aria-label="بستن" onClick={onClose} />
      <section className="management-dialog" role="dialog" aria-modal="true" aria-label={title}>
        <div className="management-dialog-head"><div><span>Workflow</span><h2>{title}</h2></div><button type="button" onClick={onClose}>بستن</button></div>
        {children}
      </section>
    </div>
  );
}
