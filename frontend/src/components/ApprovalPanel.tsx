import { TaskApproval } from "../api/client";

type Props = {
  approvals: TaskApproval[];
  taskId?: string;
  onApprove: (approvalId: string) => Promise<void>;
  onReject: (approvalId: string) => Promise<void>;
};

export function ApprovalPanel({ approvals, taskId, onApprove, onReject }: Props) {
  const pending = approvals.filter((approval) => approval.status === "pending");
  return (
    <section className="panel approvals">
      <div className="panel-heading">
        <h2>审批</h2>
        <span>{pending.length} pending</span>
      </div>
      {!taskId || pending.length === 0 ? (
        <p className="empty">没有待审批事项。</p>
      ) : (
        pending.map((approval) => (
          <article className="approval" key={approval.id}>
            <div>
              <strong>{approval.approval_type}</strong>
              <span>{approval.subject_type}</span>
            </div>
            <pre>{JSON.stringify(approval.requested_payload, null, 2)}</pre>
            <div className="actions">
              <button onClick={() => onApprove(approval.id)}>批准</button>
              <button className="secondary" onClick={() => onReject(approval.id)}>拒绝</button>
            </div>
          </article>
        ))
      )}
    </section>
  );
}
