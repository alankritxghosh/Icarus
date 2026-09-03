// Mirrors demo/decision_ledger.py's real shapes exactly -- nothing here is
// invented. `Candidate` is one item from GET /agent-mode/candidates
// (DecisionLedger.candidates + server.py's `_public_decision`); `Confirmed`
// is one item from GET /agent-mode/context (DecisionLedger.project_context).

export type Alternative = { decision: string; rationale: string };

export type Proposal = {
  repo: string;
  decision_id: string;
  branch: string;
  path: string;
  file_url: string;
  pull_request_url: string;
};

export type CandidateStatus = "pending" | "not_sure" | "confirmed_proposal" | "rejected";

export type Candidate = {
  id: string;
  repo: string;
  decision: string;
  rationale: string;
  alternatives: Alternative[];
  affected_paths: string[];
  status: CandidateStatus;
  ts: number;
  // Present only once resolved (DecisionLedger.confirm's merged event).
  selection?: "recommended" | "alternative" | "other" | "not_sure" | "reject";
  selected_decision?: string | null;
  selected_rationale?: string | null;
  proposal?: Proposal | null;
};

export type ConfirmedStatus = "human_confirmed_merged" | "human_confirmed_proposal_not_indexed";

export type Confirmed = {
  id: string;
  decision: string;
  rationale: string | null;
  affected_paths: string[];
  status: ConfirmedStatus;
  citation_ref?: string;
  citation_url?: string;
  commit?: string;
  pull_request_url?: string;
};
