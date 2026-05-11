import { useEffect, useState } from "react";
import {
  approve,
  AuditEvent,
  createTask,
  getEvents,
  getTask,
  reject,
  selectCandidate,
  TaskEnvelope
} from "./api/client";
import { ApprovalPanel } from "./components/ApprovalPanel";
import { CandidateList } from "./components/CandidateList";
import { CommandForm } from "./components/CommandForm";
import { TaskTimeline } from "./components/TaskTimeline";
import { UploadItemList } from "./components/UploadItemList";
import "./styles.css";

export default function App() {
  const [envelope, setEnvelope] = useState<TaskEnvelope | undefined>();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    if (!envelope?.task.id) return;
    const timer = window.setInterval(() => refresh(envelope.task.id), 3000);
    return () => window.clearInterval(timer);
  }, [envelope?.task.id]);

  async function refresh(taskId: string) {
    const [nextEnvelope, nextEvents] = await Promise.all([getTask(taskId), getEvents(taskId)]);
    setEnvelope(nextEnvelope);
    setEvents(nextEvents.events);
  }

  async function run(action: () => Promise<TaskEnvelope>) {
    setLoading(true);
    setError(undefined);
    try {
      const next = await action();
      setEnvelope(next);
      if (next.task.id) {
        const nextEvents = await getEvents(next.task.id);
        setEvents(nextEvents.events);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="console-shell">
      <header>
        <div>
          <p className="eyebrow">Controlled Agent Operations</p>
          <h1>广告任务控制台</h1>
        </div>
        <span className="env">mock backend</span>
      </header>
      <div className="layout">
        <aside>
          <CommandForm loading={loading} onSubmit={(command) => run(() => createTask(command))} />
          {error && <div className="error">{error}</div>}
        </aside>
        <section className="workspace">
          <TaskTimeline task={envelope?.task} events={events} />
          <ApprovalPanel
            taskId={envelope?.task.id}
            approvals={envelope?.approvals || []}
            onApprove={(approvalId) => run(() => approve(envelope!.task.id, approvalId))}
            onReject={(approvalId) => run(() => reject(envelope!.task.id, approvalId, "Rejected in console"))}
          />
          <CandidateList
            candidates={envelope?.candidates || []}
            onSelect={(candidateId) => run(() => selectCandidate(envelope!.task.id, candidateId))}
          />
          <UploadItemList items={envelope?.upload_items || []} />
        </section>
      </div>
    </main>
  );
}
