from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from qualification_bundle import DOCUMENT_TYPE_RESULT, validate_result
from qualification_review import validate_review, verify_artifacts

DOCUMENT_TYPE_STATUS = "org.upp.external-qualification-status"
SCHEMA_VERSION = 1
_VALID_STATUS = frozenset({"pending", "awaiting-review", "approved", "rejected", "needs-evidence", "invalid"})


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _bounded_reason(exc: Exception) -> str:
    text = str(exc).strip().replace("\n", " ") or exc.__class__.__name__
    return text[:256]


def summarize_submissions(*, plan: dict[str, Any], submissions_root: Path,
                          review_key_file: Path) -> dict[str, Any]:
    root = Path(submissions_root).resolve()
    if not root.exists():
        root.mkdir(parents=True)
    if not root.is_dir():
        raise ValueError("qualification submissions root must be a directory")
    rows: list[dict[str, Any]] = []
    counts = {name: 0 for name in _VALID_STATUS}
    for task in plan.get("tasks", []):
        task_id = str(task["taskId"])
        task_dir = root / task_id
        result_path = task_dir / "result.json"
        review_path = task_dir / "review.json"
        artifacts_dir = task_dir / "artifacts"
        row = {"taskId": task_id, "backlogIds": list(task["backlogIds"]),
               "status": "pending", "eligibleForBacklogReview": False}
        if not result_path.exists():
            counts["pending"] += 1; rows.append(row); continue
        if not review_path.exists():
            try:
                result = _read_object(result_path)
                validate_result(plan, result)
                verify_artifacts(result, artifacts_dir)
                row["status"] = "awaiting-review"
            except Exception as exc:
                row["status"] = "invalid"; row["reason"] = _bounded_reason(exc)
            counts[row["status"]] += 1; rows.append(row); continue
        try:
            result = _read_object(result_path)
            if result.get("documentType") != DOCUMENT_TYPE_RESULT:
                raise ValueError("invalid qualification result document")
            validate_result(plan, result)
            current_artifacts = verify_artifacts(result, artifacts_dir)
            review = _read_object(review_path)
            accepted = validate_review(plan=plan, result=result, review=review, review_key_file=review_key_file)
            if review.get("artifactVerification") != current_artifacts:
                raise ValueError("qualification evidence changed after review")
            decision = accepted["decision"]
            status = {"approve": "approved", "reject": "rejected", "needs-evidence": "needs-evidence"}.get(decision)
            if status is None:
                raise ValueError("invalid qualification review decision")
            if status == "approved" and not accepted["eligibleForBacklogReview"]:
                raise ValueError("approved qualification review is not backlog-review eligible")
            row.update({"status": status,
                        "eligibleForBacklogReview": bool(accepted["eligibleForBacklogReview"]),
                        "resultSha256": accepted["resultSha256"],
                        "reviewerIdHash": accepted["reviewerIdHash"]})
        except Exception as exc:
            row["status"] = "invalid"; row["reason"] = _bounded_reason(exc)
        counts[row["status"]] += 1; rows.append(row)
    return {
        "documentType": DOCUMENT_TYPE_STATUS,
        "schemaVersion": SCHEMA_VERSION,
        "planId": plan["planId"],
        "build": dict(plan["build"]),
        "tasks": rows,
        "counts": counts,
        "allTasksApproved": bool(rows) and all(row["status"] == "approved" for row in rows),
        "physicalOutputsArmed": False,
    }
