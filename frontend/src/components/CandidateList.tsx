import { TaskCandidate } from "../api/client";

type Props = {
  candidates: TaskCandidate[];
  onSelect: (candidateId: string) => Promise<void>;
};

export function CandidateList({ candidates, onSelect }: Props) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>候选项</h2>
        <span>{candidates.length}</span>
      </div>
      {candidates.length === 0 ? (
        <p className="empty">没有需要选择的候选项。</p>
      ) : (
        <div className="candidate-list">
          {candidates.map((candidate) => (
            <button
              className="candidate"
              key={candidate.id}
              onClick={() => onSelect(candidate.id)}
              disabled={candidate.selection_status === "selected"}
            >
              <span>{candidate.display_name}</span>
              <small>{candidate.selection_status}</small>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
