from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from backend.app.workflows.state import ApprovalStatus, ApprovalType, TaskApproval


SAVE_APPROVAL_HASH_KEY = "pending_save_report_hash"
SAVE_APPROVAL_HASH_ALGORITHM = "sha256"


class ApprovalGateError(Exception):
    """Raised when a save approval does not authorize the current payload."""


def compute_approval_payload_hash(payload: Any) -> str:
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def build_save_approval_request(pending_save_report: dict[str, Any]) -> dict[str, str]:
    return {
        "hash_algorithm": SAVE_APPROVAL_HASH_ALGORITHM,
        SAVE_APPROVAL_HASH_KEY: compute_approval_payload_hash(pending_save_report),
    }


def verify_save_approval(approval: TaskApproval, current_pending_save_report: dict[str, Any]) -> None:
    if approval.approval_type is not ApprovalType.SAVE_APPROVAL:
        raise ApprovalGateError("save_approval record is required before saving")
    if approval.status is not ApprovalStatus.APPROVED:
        raise ApprovalGateError("save approval must be approved before saving")

    approved_hash = approval.requested_payload.get(SAVE_APPROVAL_HASH_KEY)
    if not isinstance(approved_hash, str) or not approved_hash:
        raise ApprovalGateError("save approval is missing pending report hash")

    current_hash = compute_approval_payload_hash(current_pending_save_report)
    if not hmac.compare_digest(approved_hash, current_hash):
        raise ApprovalGateError("save approval hash does not match current pending report")
