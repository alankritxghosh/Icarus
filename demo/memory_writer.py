"""Bounded GitHub writer for a human-authored engineering-memory record.

This module does not merge, edit, or delete anything. One explicit call may
create one branch, one new Markdown file, and one pull request. GitHub remains
the authority for review and acceptance.
"""

import base64
import hashlib
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import PurePosixPath


_API = "https://api.github.com/repos"
_USER_AGENT = "icarus/0.1"
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GAP_ID_RE = re.compile(r"^[0-9a-f]{64}$")


class MemoryWriteError(Exception):
    """A truthful, client-safe failure with an optional recoverable artifact."""

    def __init__(self, message, *, status=502, recovery_url=None):
        super().__init__(message)
        self.status = status
        self.recovery_url = recovery_url


def _default_opener(request, timeout):
    return urllib.request.urlopen(request, timeout=timeout)


def _clean_text(value, name, maximum, *, required=False, single_line=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise MemoryWriteError(f"{name} must be text", status=400)
    value = value.strip()
    if required and not value:
        raise MemoryWriteError(f"{name} is required", status=400)
    if len(value) > maximum:
        raise MemoryWriteError(f"{name} is too long", status=400)
    if "\x00" in value or (single_line and ("\n" in value or "\r" in value)):
        raise MemoryWriteError(f"{name} contains unsupported characters", status=400)
    return value


class GitHubMemoryWriter:
    """Create one reviewable memory proposal using the caller's GitHub token."""

    def __init__(self, opener=None, timeout=15.0):
        self._opener = opener or _default_opener
        self._timeout = timeout

    def _request(self, method, url, token, body=None, *, expected):
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": _USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url, data=data, headers=headers, method=method,
        )
        response = None
        try:
            response = self._opener(request, self._timeout)
        except urllib.error.HTTPError as error:
            if error.code not in expected:
                raise MemoryWriteError("GitHub refused the memory record") from error
            response = error
        except MemoryWriteError:
            raise
        except (
            urllib.error.URLError,
            OSError,
            ValueError,
            TypeError,
            http.client.HTTPException,
        ) as error:
            raise MemoryWriteError("GitHub could not create the memory record") from error
        with response:
            status = getattr(response, "status", getattr(response, "code", None))
            if status not in expected:
                raise MemoryWriteError("GitHub refused the memory record")
            try:
                decoded = json.loads(response.read())
            except (ValueError, TypeError) as error:
                raise MemoryWriteError("GitHub returned an invalid response") from error
        if not isinstance(decoded, (dict, list)):
            raise MemoryWriteError("GitHub returned an invalid response")
        return status, decoded

    def record(self, *, repo, token, gap_id, question, rationale,
               tradeoffs="", references=()):
        """Create the bounded proposal and return only observed GitHub URLs."""
        repo, token = self._validated_target(repo, token)
        if not isinstance(gap_id, str) or not _GAP_ID_RE.fullmatch(gap_id):
            raise MemoryWriteError("invalid engineering-memory gap", status=400)
        question = _clean_text(question, "question", 500, required=True)
        rationale = _clean_text(rationale, "rationale", 8_000, required=True)
        tradeoffs = _clean_text(tradeoffs, "tradeoffs", 4_000)
        if not isinstance(references, list | tuple):
            raise MemoryWriteError("references must be a list", status=400)
        cleaned_refs = [
            _clean_text(item, "reference", 500, required=True)
            for item in references
        ]
        if sum(map(len, cleaned_refs)) > 4_000:
            raise MemoryWriteError("references are too long", status=400)

        sections = [
            f"# {question}",
            "",
            "> Retrospective record: this rationale was recorded after the original decision.",
            "",
            "## Recorded rationale",
            "",
            rationale,
            "",
            "## Accepted tradeoffs and consequences",
            "",
            tradeoffs or "Not recorded.",
            "",
            "## Related evidence",
            "",
        ]
        sections.extend(
            [f"- {reference}" for reference in cleaned_refs]
            or ["No related evidence was supplied with this record."]
        )
        sections.extend([
            "",
            "---",
            "",
            "Proposed through Icarus Engineering Memory. Review and merge history in GitHub are authoritative.",
            "",
        ])
        markdown = "\n".join(sections)

        question_id = hashlib.sha256(question.casefold().encode()).hexdigest()[:12]
        return self._record_document(
            repo=repo,
            token=token,
            record_id=gap_id,
            branch_kind="memory",
            title=question,
            markdown=markdown,
            commit_message=f"docs: record engineering memory for {question_id}",
            pull_title=f"Record engineering memory: {question[:72]}",
            pull_body=(
                "This pull request records previously undocumented "
                "engineering rationale identified as an Icarus Memory Gap.\n\n"
                "Review the rationale as a team before merging. Icarus will "
                "not treat it as accepted memory until it is merged and "
                "re-indexed."
            ),
            result_fields={"question": question},
        )

    def record_decision(self, *, repo, token, decision_id, decision,
                        rationale=None, alternatives=(), affected_paths=()):
        """Propose one human-confirmed live decision for repository review."""
        repo, token = self._validated_target(repo, token)
        if not isinstance(decision_id, str) or not _GAP_ID_RE.fullmatch(decision_id):
            raise MemoryWriteError("invalid decision candidate", status=400)
        decision = _clean_text(
            decision, "decision", 280, required=True, single_line=True)
        rationale = _clean_text(
            rationale, "rationale", 1000, single_line=True)
        if not isinstance(alternatives, list | tuple) or len(alternatives) > 3:
            raise MemoryWriteError("alternatives must be a short list", status=400)
        alternatives = [
            _clean_text(
                value, "alternative", 280, required=True, single_line=True)
            for value in alternatives
        ]
        if not isinstance(affected_paths, list | tuple) or len(affected_paths) > 20:
            raise MemoryWriteError("affected_paths must be a short list", status=400)
        paths = []
        for value in affected_paths:
            cleaned = _clean_text(
                value, "affected path", 500, required=True, single_line=True)
            parsed = PurePosixPath(cleaned)
            if parsed.is_absolute() or ".." in parsed.parts:
                raise MemoryWriteError(
                    "affected paths must be repository-relative", status=400)
            paths.append(cleaned)

        sections = [
            f"<!-- icarus-agent-mode-decision:v1 id={decision_id} -->",
            "",
            f"# {decision}",
            "",
            "> Human-confirmed decision proposal. This is not merged project truth.",
            "",
            "## Decision",
            "",
            decision,
            "",
            "## Confirmed rationale",
            "",
            rationale or "No rationale was confirmed.",
            "",
            "## Alternatives considered",
            "",
        ]
        sections.extend([f"- {value}" for value in alternatives]
                        or ["No alternatives were recorded."])
        sections.extend(["", "## Affected paths", ""])
        sections.extend([f"- `{value}`" for value in paths]
                        or ["No affected paths were recorded."])
        sections.extend([
            "",
            "---",
            "",
            "Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.",
            "",
        ])
        markdown = "\n".join(sections)
        return self._record_document(
            repo=repo,
            token=token,
            record_id=decision_id,
            branch_kind="decision",
            title=decision,
            markdown=markdown,
            commit_message=f"docs: propose project decision {decision_id[:12]}",
            pull_title=f"Record project decision: {decision[:72]}",
            pull_body=(
                "This is a human-confirmed Icarus Agent Mode decision proposal.\n\n"
                "It is not accepted project memory until repository review, "
                "merge, and re-index complete."
            ),
            result_fields={"decision_id": decision_id},
        )

    @staticmethod
    def _validated_target(repo, token):
        if not isinstance(repo, str) or not _REPO_RE.fullmatch(repo.strip()):
            raise MemoryWriteError("repo must look like owner/name", status=400)
        if not isinstance(token, str) or not token:
            raise MemoryWriteError("sign in with GitHub to continue", status=401)
        return repo.strip(), token

    def _record_document(self, *, repo, token, record_id, branch_kind, title,
                         markdown, commit_message, pull_title, pull_body,
                         result_fields):
        """The single bounded GitHub mutation path shared by both record kinds."""
        slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")[:48] or "decision"
        proposal_id = record_id[:20]
        branch = f"icarus/{branch_kind}-{proposal_id}"
        path = f"docs/engineering-memory/{proposal_id}-{slug}.md"
        repo_api = f"{_API}/{repo}"

        def result(pull_url, current_file_url):
            return {
                "repo": repo,
                **result_fields,
                "branch": branch,
                "path": path,
                "file_url": current_file_url,
                "pull_request_url": pull_url,
            }

        _status, metadata = self._request("GET", repo_api, token, expected={200})
        default_branch = metadata.get("default_branch")
        permissions = metadata.get("permissions")
        if (
            not isinstance(default_branch, str)
            or not default_branch
            or not isinstance(permissions, dict)
        ):
            raise MemoryWriteError(
                "GitHub did not return repository write permissions", status=403,
            )
        if permissions.get("push") is not True:
            raise MemoryWriteError(
                "Your GitHub account cannot create a branch in this repository",
                status=403,
            )

        branch_url = f"https://github.com/{repo}/tree/{urllib.parse.quote(branch, safe='/')}"
        file_url = (
            f"https://github.com/{repo}/blob/"
            f"{urllib.parse.quote(branch, safe='/')}/"
            f"{urllib.parse.quote(path, safe='/')}"
        )
        file_exists = False
        owner = repo.split("/", 1)[0]
        pull_query = urllib.parse.urlencode({
            "state": "all", "head": f"{owner}:{branch}", "per_page": "1",
        })
        refs_url = (
            f"{repo_api}/git/matching-refs/heads/"
            f"{urllib.parse.quote(branch, safe='')}"
        )

        def existing_pull():
            _code, pulls = self._request(
                "GET", f"{repo_api}/pulls?{pull_query}", token, expected={200},
            )
            if not isinstance(pulls, list):
                raise MemoryWriteError("GitHub returned an invalid pull request list")
            for pull in pulls:
                url = pull.get("html_url") if isinstance(pull, dict) else None
                if isinstance(url, str) and url.startswith("https://github.com/"):
                    return url
            return None

        def exact_branch_exists():
            _code, refs = self._request("GET", refs_url, token, expected={200})
            if not isinstance(refs, list):
                raise MemoryWriteError("GitHub returned an invalid branch list")
            expected_ref = f"refs/heads/{branch}"
            return any(
                isinstance(ref, dict) and ref.get("ref") == expected_ref
                for ref in refs
            )

        branch_exists = exact_branch_exists()
        if branch_exists:
            pull_url = existing_pull()
            if pull_url:
                return result(pull_url, file_url)

        try:
            if not branch_exists:
                encoded_default = urllib.parse.quote(default_branch, safe="")
                _code, head = self._request(
                    "GET", f"{repo_api}/git/ref/heads/{encoded_default}",
                    token, expected={200},
                )
                sha = (
                    (head.get("object") or {}).get("sha")
                    if isinstance(head, dict)
                    and isinstance(head.get("object"), dict)
                    else None
                )
                if not isinstance(sha, str) or not sha:
                    raise MemoryWriteError("GitHub did not return the default branch head")
                try:
                    self._request(
                        "POST", f"{repo_api}/git/refs", token,
                        {"ref": f"refs/heads/{branch}", "sha": sha},
                        expected={201},
                    )
                except MemoryWriteError:
                    if not exact_branch_exists():
                        raise
                branch_exists = True

            encoded_path = urllib.parse.quote(path, safe="/")
            query = urllib.parse.urlencode({"ref": branch})
            file_status, existing_file = self._request(
                "GET", f"{repo_api}/contents/{encoded_path}?{query}",
                token, expected={200, 404},
            )
            if file_status == 404:
                try:
                    _code, created = self._request(
                        "PUT", f"{repo_api}/contents/{encoded_path}", token,
                        {
                            "message": commit_message,
                            "content": base64.b64encode(markdown.encode()).decode(),
                            "branch": branch,
                        },
                        expected={201},
                    )
                    content = created.get("content") if isinstance(created, dict) else None
                    if isinstance(content, dict) and isinstance(content.get("html_url"), str):
                        file_url = content["html_url"]
                    file_exists = True
                except MemoryWriteError:
                    file_status, existing_file = self._request(
                        "GET", f"{repo_api}/contents/{encoded_path}?{query}",
                        token, expected={200, 404},
                    )
                    if file_status != 200:
                        raise

            if file_status == 200:
                file_exists = True
                encoded = (
                    existing_file.get("content")
                    if isinstance(existing_file, dict)
                    else None
                )
                if not isinstance(encoded, str):
                    raise MemoryWriteError(
                        "The existing memory proposal could not be verified",
                    )
                try:
                    existing_markdown = base64.b64decode(encoded).decode()
                except (ValueError, UnicodeDecodeError) as error:
                    raise MemoryWriteError(
                        "The existing memory proposal could not be verified",
                    ) from error
                if existing_markdown != markdown:
                    raise MemoryWriteError(
                        "A different memory proposal already exists for this gap",
                    )

            try:
                _code, pull = self._request(
                    "POST", f"{repo_api}/pulls", token,
                    {
                        "title": pull_title,
                        "head": branch,
                        "base": default_branch,
                        "body": pull_body,
                    },
                    expected={201},
                )
            except MemoryWriteError:
                pull_url = existing_pull()
                if not pull_url:
                    raise
                pull = {"html_url": pull_url}
        except MemoryWriteError as error:
            raise MemoryWriteError(
                str(error),
                status=502,
                recovery_url=(
                    file_url if file_exists
                    else branch_url if branch_exists
                    else None
                ),
            ) from error

        pull_url = pull.get("html_url") if isinstance(pull, dict) else None
        if not isinstance(pull_url, str) or not pull_url.startswith("https://github.com/"):
            raise MemoryWriteError(
                "GitHub created the proposal but did not return its pull request URL",
                recovery_url=file_url or branch_url,
            )
        return result(pull_url, file_url)
