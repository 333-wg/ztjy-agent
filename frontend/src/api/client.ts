export type AgentTask = {
  id: string;
  original_command: string;
  agent_key: string;
  workflow_key: string;
  status: string;
  awaiting_action?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  pending_save_report?: Record<string, unknown> | null;
};

export type TaskApproval = {
  id: string;
  task_id: string;
  approval_type: string;
  subject_type: string;
  subject_id: string;
  status: string;
  requested_payload: Record<string, unknown>;
};

export type TaskCandidate = {
  id: string;
  display_name: string;
  candidate_type: string;
  selection_status: string;
  external_ref?: string | null;
};

export type UploadItem = {
  id: string;
  item_order: number;
  requested_name: string;
  requested_type: string;
  local_asset_query?: string | null;
  status: string;
  saved_ad?: Record<string, unknown> | null;
};

export type AuditEvent = {
  id: string;
  event_type: string;
  summary: string;
  severity: string;
  created_at: string;
};

export type TaskEnvelope = {
  task: AgentTask;
  approvals: TaskApproval[];
  candidates: TaskCandidate[];
  upload_batches: Record<string, unknown>[];
  upload_items: UploadItem[];
};

export async function createTask(command: string): Promise<TaskEnvelope> {
  return requestJson("/tasks", {
    method: "POST",
    body: JSON.stringify({ command })
  });
}

export async function getTask(taskId: string): Promise<TaskEnvelope> {
  return requestJson(`/tasks/${taskId}`);
}

export async function getEvents(taskId: string): Promise<{ events: AuditEvent[] }> {
  return requestJson(`/tasks/${taskId}/events`);
}

export async function approve(taskId: string, approvalId: string): Promise<TaskEnvelope> {
  return requestJson(`/tasks/${taskId}/approvals/${approvalId}/approve`, {
    method: "POST",
    body: JSON.stringify({ decided_by: "owner" })
  });
}

export async function reject(taskId: string, approvalId: string, reason: string): Promise<TaskEnvelope> {
  return requestJson(`/tasks/${taskId}/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ decided_by: "owner", reason })
  });
}

export async function selectCandidate(taskId: string, candidateId: string): Promise<TaskEnvelope> {
  return requestJson(`/tasks/${taskId}/candidates/${candidateId}/select`, {
    method: "POST",
    body: JSON.stringify({ selected_by: "owner" })
  });
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    ...init
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
