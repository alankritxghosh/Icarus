"""Repo-scoped Agent Mode decisions, with session content kept out of memory.

The coding agent may append one bounded candidate.  Only a later explicit
human action may select it, and a selected decision is not exposed to future
sessions until GitHub has returned a reviewable proposal URL.  An open proposal
is labelled as such; merge and re-index remain the authority for project truth.
"""

import hashlib
import json
import re
import threading
import time
from pathlib import Path, PurePosixPath


_SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HEX_ID = re.compile(r"^[0-9a-f]{64}$")
_SELECTIONS = {"recommended", "alternative", "other", "not_sure", "reject"}
_DECISION_MARKER = re.compile(
    r"^<!-- icarus-agent-mode-decision:v1 id=([0-9a-f]{64}) -->$", re.MULTILINE,
)


class DecisionLedgerError(ValueError):
    """A bounded, caller-safe validation or lifecycle failure."""


def _slug(repo):
    if not isinstance(repo, str) or not _SAFE_REPO.fullmatch(repo) or ".." in repo:
        raise DecisionLedgerError("invalid repo name")
    return repo.replace("/", "__")


def _text(value, name, maximum, *, required=True, single_line=False):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise DecisionLedgerError(f"{name} must be text")
    cleaned = value.strip()
    if required and not cleaned:
        raise DecisionLedgerError(f"{name} is required")
    if (
        len(cleaned) > maximum
        or "\x00" in cleaned
        or (single_line and ("\n" in cleaned or "\r" in cleaned))
    ):
        raise DecisionLedgerError(f"{name} is too long or invalid")
    return cleaned or None


def _path(value):
    cleaned = _text(value, "affected path", 500, single_line=True)
    parsed = PurePosixPath(cleaned)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise DecisionLedgerError("affected paths must be repository-relative")
    return cleaned


class DecisionLedger:
    """Append-only decision candidates and human lifecycle events."""

    def __init__(self, root, clock=time.time):
        self._root = Path(root)
        self._clock = clock
        self._lock = threading.RLock()

    def _file(self, repo):
        return self._root / f"{_slug(repo.casefold())}.jsonl"

    def submit(self, repo, *, session_id, decision, rationale, alternatives,
               affected_paths=(), **unknown):
        if unknown:
            raise DecisionLedgerError(
                "unsupported candidate fields: " + ", ".join(sorted(unknown)))
        session = _text(session_id, "session_id", 500, single_line=True)
        decision = _text(decision, "decision", 280, single_line=True)
        rationale = _text(rationale, "rationale", 1000, single_line=True)
        if not isinstance(alternatives, list) or not 1 <= len(alternatives) <= 3:
            raise DecisionLedgerError("alternatives must contain one to three choices")
        cleaned_alternatives = []
        for alternative in alternatives:
            if not isinstance(alternative, dict) or set(alternative) != {
                "decision", "rationale",
            }:
                raise DecisionLedgerError(
                    "each alternative must contain only decision and rationale")
            cleaned_alternatives.append({
                "decision": _text(
                    alternative["decision"], "alternative decision", 280,
                    single_line=True,
                ),
                "rationale": _text(
                    alternative["rationale"], "alternative rationale", 1000,
                    single_line=True,
                ),
            })
        if not isinstance(affected_paths, list | tuple) or len(affected_paths) > 20:
            raise DecisionLedgerError("affected_paths must contain at most 20 paths")
        cleaned_paths = [_path(value) for value in affected_paths]

        fingerprint = hashlib.sha256(session.encode()).hexdigest()
        identity = {
            "repo": repo.casefold(),
            "session_fingerprint": fingerprint,
            "decision": decision,
            "rationale": rationale,
            "alternatives": cleaned_alternatives,
            "affected_paths": cleaned_paths,
        }
        candidate_id = hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode()
        ).hexdigest()
        with self._lock:
            existing = next((
                item for item in self.candidates(repo, statuses=None)
                if item["id"] == candidate_id
            ), None)
            if existing is not None:
                return existing

            entry = {
                "event": "candidate",
                "ts": self._clock(),
                "id": candidate_id,
                "source": "claude_code",
                "session_fingerprint": fingerprint,
                "decision": decision,
                "rationale": rationale,
                "alternatives": cleaned_alternatives,
                "affected_paths": cleaned_paths,
            }
            self._append(repo, entry)
            return {**entry, "status": "pending"}

    def confirm(self, repo, *, candidate_id, selection, alternative_index=None,
                other_text=None, proposal=None):
        with self._lock:
            current = next((
                item for item in self.candidates(repo, statuses=None)
                if item["id"] == candidate_id
            ), None)
            if current is not None and self._same_resolution(
                current,
                selection=selection,
                alternative_index=alternative_index,
                other_text=other_text,
            ):
                return current

            preview = self.preview_confirmation(
                repo,
                candidate_id=candidate_id,
                selection=selection,
                alternative_index=alternative_index,
                other_text=other_text,
            )
            current = preview["candidate"]
            selected_decision = preview["decision"]
            selected_rationale = preview["rationale"]
            status = preview["status"]

            if status == "confirmed_proposal":
                proposal = self._validated_proposal(repo, candidate_id, proposal)
            elif proposal is not None:
                raise DecisionLedgerError("unconfirmed decisions cannot carry a proposal")

            event = {
                "event": "confirmation",
                "ts": self._clock(),
                "id": candidate_id,
                "status": status,
                "selection": selection,
                "selected_decision": selected_decision,
                "selected_rationale": selected_rationale,
                "proposal": proposal,
            }
            self._append(repo, event)
            return {**current, **event}

    @staticmethod
    def _same_resolution(current, *, selection, alternative_index, other_text):
        if current.get("selection") != selection:
            return False
        if selection in {"recommended", "not_sure", "reject"}:
            return True
        if selection == "alternative":
            if (
                isinstance(alternative_index, bool)
                or not isinstance(alternative_index, int)
                or not 0 <= alternative_index < len(current.get("alternatives", ()))
            ):
                return False
            return (
                current.get("selected_decision")
                == current["alternatives"][alternative_index].get("decision")
            )
        if selection == "other":
            try:
                cleaned = _text(other_text, "other_text", 1000, single_line=True)
            except DecisionLedgerError:
                return False
            return current.get("selected_decision") == cleaned
        return False

    def preview_confirmation(self, repo, *, candidate_id, selection,
                             alternative_index=None, other_text=None):
        """Validate a human choice before the caller performs the GitHub write."""
        if not isinstance(candidate_id, str) or not _HEX_ID.fullmatch(candidate_id):
            raise DecisionLedgerError("invalid candidate id")
        if selection not in _SELECTIONS:
            raise DecisionLedgerError("invalid confirmation selection")
        current = next((
            item for item in self.candidates(repo, statuses=None)
            if item["id"] == candidate_id
        ), None)
        if current is None:
            raise DecisionLedgerError("unknown decision candidate")
        if current["status"] not in ("pending", "not_sure"):
            raise DecisionLedgerError("decision candidate is already resolved")

        selected_decision = None
        selected_rationale = None
        status = "rejected" if selection == "reject" else selection
        if selection == "recommended":
            selected_decision = current["decision"]
            selected_rationale = current["rationale"]
            status = "confirmed_proposal"
        elif selection == "alternative":
            if (isinstance(alternative_index, bool)
                    or not isinstance(alternative_index, int)
                    or not 0 <= alternative_index < len(current["alternatives"])):
                raise DecisionLedgerError("alternative_index is invalid")
            selected = current["alternatives"][alternative_index]
            selected_decision = selected["decision"]
            selected_rationale = selected["rationale"]
            status = "confirmed_proposal"
        elif selection == "other":
            selected_decision = _text(
                other_text, "other_text", 1000, single_line=True)
            # The person supplied a decision, not necessarily a rationale.  Do
            # not inherit the agent's rejected explanation or invent one.
            selected_rationale = None
            status = "confirmed_proposal"

        considered = [current["decision"]] + [
            item["decision"] for item in current["alternatives"]
        ]
        alternatives = [value for value in considered if value != selected_decision]
        return {
            "candidate": current,
            "status": status,
            "decision": selected_decision,
            "rationale": selected_rationale,
            "alternatives": alternatives[:3],
            "affected_paths": current["affected_paths"],
        }

    def candidates(self, repo, *, statuses={"pending"}):
        state = {}
        order = []
        for event in self._events(repo):
            candidate_id = event.get("id")
            if not isinstance(candidate_id, str):
                continue
            if event.get("event") == "candidate":
                state[candidate_id] = {**event, "status": "pending"}
                order.append(candidate_id)
            elif event.get("event") == "confirmation" and candidate_id in state:
                state[candidate_id].update(event)
        items = [state[item] for item in reversed(order)]
        if statuses is None:
            return items
        allowed = set(statuses)
        return [item for item in items if item.get("status") in allowed]

    def project_context(self, repo, *, limit=20, indexed_chunks=(), commit=None):
        """Project confirmed intent without confusing proposals with truth.

        A local confirmation backed by an observed GitHub pull request is
        available as a proposal that is not present in indexed truth. Absence
        from the corpus does not prove the pull request is still open. Only a
        generated decision document found in the active indexed corpus is
        promoted to merged, cited project memory. Parsing those documents also
        lets merged intent survive loss of this local operational ledger.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise DecisionLedgerError("project context limit must be between 1 and 20")
        indexed = self._indexed_decisions(indexed_chunks, commit=commit)
        context = []
        seen = set()
        for item in self.candidates(
            repo, statuses={"confirmed_proposal"},
        ):
            proposal = item["proposal"]
            merged = indexed.get(item["id"])
            if merged is not None and merged["path"] == proposal["path"]:
                context.append({
                    "id": item["id"],
                    "decision": item["selected_decision"],
                    "rationale": item["selected_rationale"],
                    "affected_paths": item["affected_paths"],
                    "status": "human_confirmed_merged",
                    "citation_ref": merged["citation_ref"],
                    **({"commit": commit} if commit else {}),
                })
            else:
                context.append({
                    "id": item["id"],
                    "decision": item["selected_decision"],
                    "rationale": item["selected_rationale"],
                    "affected_paths": item["affected_paths"],
                    "status": "human_confirmed_proposal_not_indexed",
                    "pull_request_url": proposal["pull_request_url"],
                })
            seen.add(item["id"])
            if len(context) == limit:
                return context

        # A merged record is the durable authority.  Recover it even when the
        # local candidate ledger was lost on restart; ordinary or unmarked
        # engineering docs never enter this path.
        for candidate_id in sorted(indexed):
            if candidate_id in seen:
                continue
            record = indexed[candidate_id]
            context.append({
                "id": candidate_id,
                "decision": record["decision"],
                "rationale": record["rationale"],
                "affected_paths": record["affected_paths"],
                "status": "human_confirmed_merged",
                "citation_ref": record["citation_ref"],
                **({"commit": commit} if commit else {}),
            })
            if len(context) == limit:
                break
        return context

    @staticmethod
    def _indexed_decisions(chunks, *, commit=None):
        records = {}
        ordered = sorted(
            chunks or (), key=lambda chunk: getattr(chunk, "ref", ""),
        )
        for chunk in ordered:
            ref = getattr(chunk, "ref", None)
            source = getattr(chunk, "source", None)
            text = getattr(chunk, "text", None)
            if not (
                isinstance(ref, str)
                and source == "doc"
                and ref.startswith("doc:docs/engineering-memory/")
                and isinstance(text, str)
            ):
                continue
            marker = _DECISION_MARKER.search(text)
            if marker is None:
                continue
            candidate_id = marker.group(1)
            decision = DecisionLedger._markdown_section(text, "Decision")
            rationale = DecisionLedger._markdown_section(text, "Confirmed rationale")
            affected = DecisionLedger._markdown_section(text, "Affected paths")
            if decision is None or rationale is None or affected is None:
                continue
            try:
                decision = _text(
                    decision, "indexed decision", 280, single_line=True)
                rationale = (
                    None
                    if rationale == "No rationale was confirmed."
                    else _text(
                        rationale, "indexed rationale", 1000, single_line=True)
                )
            except DecisionLedgerError:
                continue
            paths = []
            valid = True
            # A ranged ref is one window of a larger document. Its visible
            # path bullets may be only a prefix, so reconstruct no path list
            # rather than presenting a partial list as complete.
            if "#" not in ref.split(":", 1)[1]:
                for line in affected.splitlines():
                    match = re.fullmatch(r"- `([^`]+)`", line.strip())
                    if match:
                        try:
                            paths.append(_path(match.group(1)))
                        except DecisionLedgerError:
                            valid = False
                            break
            if not valid or len(paths) > 20:
                continue
            path = ref.split(":", 1)[1].split("#", 1)[0]
            records.setdefault(candidate_id, {
                "path": path,
                "decision": decision,
                "rationale": rationale,
                "affected_paths": paths,
                "citation_ref": ref,
            })
        return records

    @staticmethod
    def _markdown_section(text, heading):
        match = re.search(
            rf"^## {re.escape(heading)}\s*$\n+(.*?)(?=^## |^---\s*$|\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        if match is None:
            return None
        value = match.group(1).strip()
        return value or None

    def _events(self, repo):
        path = self._file(repo)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, OSError):
            return []
        events = []
        for line in lines:
            try:
                event = json.loads(line)
            except (TypeError, ValueError):
                continue
            if isinstance(event, dict):
                events.append(event)
        return events

    def _append(self, repo, entry):
        path = self._file(repo)
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
        try:
            with self._lock:
                self._root.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(line)
        except OSError as error:
            raise DecisionLedgerError("decision memory could not be persisted") from error

    @staticmethod
    def _validated_proposal(repo, candidate_id, proposal):
        if not isinstance(proposal, dict):
            raise DecisionLedgerError("a reviewed GitHub proposal is required")
        expected = {
            "repo", "decision_id", "branch", "path", "file_url", "pull_request_url",
        }
        if set(proposal) != expected:
            raise DecisionLedgerError("invalid reviewed GitHub proposal")
        valid = (
            proposal["repo"] == repo
            and proposal["decision_id"] == candidate_id
            and all(isinstance(proposal[key], str) and proposal[key]
                    for key in ("branch", "path", "file_url", "pull_request_url"))
            and proposal["file_url"].startswith("https://github.com/")
            and proposal["pull_request_url"].startswith("https://github.com/")
        )
        if not valid:
            raise DecisionLedgerError("invalid reviewed GitHub proposal")
        return dict(proposal)
