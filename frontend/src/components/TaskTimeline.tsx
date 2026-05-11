import { AuditEvent, AgentTask } from "../api/client";

type Props = {
  task?: AgentTask;
  events: AuditEvent[];
};

export function TaskTimeline({ task, events }: Props) {
  return (
    <section className="panel timeline">
      <div className="panel-heading">
        <h2>任务状态</h2>
        <span className={`status ${task?.status || "idle"}`}>{task?.status || "idle"}</span>
      </div>
      {task ? (
        <dl className="task-meta">
          <div><dt>Agent</dt><dd>{task.agent_key}</dd></div>
          <div><dt>Workflow</dt><dd>{task.workflow_key}</dd></div>
          <div><dt>等待动作</dt><dd>{task.awaiting_action || "-"}</dd></div>
        </dl>
      ) : (
        <p className="empty">等待第一条任务命令。</p>
      )}
      <ol className="events">
        {events.map((event) => (
          <li key={event.id}>
            <span>{event.event_type}</span>
            <p>{event.summary}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
