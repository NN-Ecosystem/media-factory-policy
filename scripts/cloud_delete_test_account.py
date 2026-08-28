#!/usr/bin/env python3
"""Safely preview/delete a Cloud Foundation test account by email.

Default mode is dry-run. Nothing is deleted unless --confirm is supplied.

Deletes Cloud Foundation identity graph owned by the resolved user_id:
  - cloud_users/<user_id>
  - cloud_user_emails/<sha256(normalized_email)>
  - user_trials/<user_id>
  - entitlements where subject_id == user_id
  - core_registrations where user_id == user_id
  - cloud_onboarding_sessions where user_id == user_id
  - email_verifications where user_id == user_id

Audit events are retained by default for traceability. Use --include-audit only for
non-production test cleanup when you intentionally want those removed too.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def _bootstrap_repo_root() -> Path:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


ROOT = _bootstrap_repo_root()


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _load_cred_file(path: str | None) -> None:
    if not path:
        return
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise SystemExit(f"Firebase credential file not found: {p}")
    raw = p.read_text(encoding="utf-8")
    # Validate early so malformed files do not reach firebase_admin.
    json.loads(raw)
    os.environ["FIREBASE_CRED"] = raw


def _doc_rows(query) -> List[Tuple[str, Dict]]:
    rows: List[Tuple[str, Dict]] = []
    for snap in query.stream():
        rows.append((snap.id, snap.to_dict() or {}))
    return rows


def _resolve(db, email: str, include_audit: bool) -> Dict:
    normalized = _normalize_email(email)
    email_index_id = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    idx_ref = db.collection("cloud_user_emails").document(email_index_id)
    idx = idx_ref.get()

    user_id = None
    if idx.exists:
        user_id = str((idx.to_dict() or {}).get("user_id") or "").strip() or None

    # Recovery path if the email index was already damaged/removed.
    user_rows = _doc_rows(db.collection("cloud_users").where("email_normalized", "==", normalized))
    if not user_id and user_rows:
        user_id = user_rows[0][0]

    plan: Dict = {
        "email": normalized,
        "email_index_id": email_index_id,
        "user_id": user_id,
        "documents": [],
    }

    def add(collection: str, doc_id: str, data: Dict | None = None):
        plan["documents"].append({"collection": collection, "doc_id": doc_id, "data": data or {}})

    if idx.exists:
        add("cloud_user_emails", email_index_id, idx.to_dict() or {})

    if not user_id:
        return plan

    user_ref = db.collection("cloud_users").document(user_id)
    user_snap = user_ref.get()
    if user_snap.exists:
        add("cloud_users", user_id, user_snap.to_dict() or {})

    trial_snap = db.collection("user_trials").document(user_id).get()
    if trial_snap.exists:
        add("user_trials", user_id, trial_snap.to_dict() or {})

    for doc_id, data in _doc_rows(db.collection("entitlements").where("subject_id", "==", user_id)):
        add("entitlements", doc_id, data)

    for doc_id, data in _doc_rows(db.collection("entitlement_activations").where("user_id", "==", user_id)):
        add("entitlement_activations", doc_id, data)

    for doc_id, data in _doc_rows(db.collection("core_registrations").where("user_id", "==", user_id)):
        add("core_registrations", doc_id, data)

    for doc_id, data in _doc_rows(db.collection("cloud_onboarding_sessions").where("user_id", "==", user_id)):
        add("cloud_onboarding_sessions", doc_id, data)

    for doc_id, data in _doc_rows(db.collection("email_verifications").where("user_id", "==", user_id)):
        add("email_verifications", doc_id, data)

    if include_audit:
        for doc_id, data in _doc_rows(db.collection("audit_events").where("subject_id", "==", user_id)):
            add("audit_events", doc_id, data)

    return plan


def _print_plan(plan: Dict) -> None:
    print(json.dumps({
        "email": plan["email"],
        "user_id": plan["user_id"],
        "document_count": len(plan["documents"]),
        "documents": [
            {
                "collection": row["collection"],
                "doc_id": row["doc_id"],
                "status": row.get("data", {}).get("status"),
                "product": row.get("data", {}).get("product"),
                "plan": row.get("data", {}).get("plan"),
                "core_id": row.get("data", {}).get("core_id"),
                "purpose": row.get("data", {}).get("purpose"),
            }
            for row in plan["documents"]
        ],
    }, indent=2, ensure_ascii=False))


def _delete(db, plan: Dict) -> None:
    # Delete dependent documents first; identity/index last.
    priority = {
        "audit_events": 10,
        "email_verifications": 20,
        "cloud_onboarding_sessions": 30,
        "entitlement_activations": 30,
        "core_registrations": 40,
        "entitlements": 50,
        "user_trials": 60,
        "cloud_users": 90,
        "cloud_user_emails": 100,
    }
    rows = sorted(plan["documents"], key=lambda r: priority.get(r["collection"], 50))
    for row in rows:
        db.collection(row["collection"]).document(row["doc_id"]).delete()
        print(f"DELETED {row['collection']}/{row['doc_id']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview/delete a Core Factory Cloud test account by email.")
    parser.add_argument("--email", required=True, help="Exact test account email to reset")
    parser.add_argument("--confirm", action="store_true", help="Actually delete. Without this flag, only preview.")
    parser.add_argument("--include-audit", action="store_true", help="Also delete audit_events for this user_id (normally retained).")
    parser.add_argument("--firebase-cred-file", help="Optional Firebase service-account JSON file. Otherwise FIREBASE_CRED must be set.")
    args = parser.parse_args()

    email = _normalize_email(args.email)
    if not email or "@" not in email:
        raise SystemExit("A valid --email is required")

    _load_cred_file(args.firebase_cred_file)
    if not os.getenv("FIREBASE_CRED"):
        raise SystemExit("FIREBASE_CRED is not set. Set it or pass --firebase-cred-file <service-account.json>.")

    from server.db.firebase import get_db

    db = get_db()
    plan = _resolve(db, email=email, include_audit=args.include_audit)
    _print_plan(plan)

    if not plan["user_id"]:
        print("RESULT account_not_found")
        return 0

    if not args.confirm:
        print("DRY RUN ONLY — no documents deleted. Re-run with --confirm to delete this test account.")
        return 0

    # Explicit confirmation guard: command email must still match the resolved user record.
    user_snap = db.collection("cloud_users").document(plan["user_id"]).get()
    if user_snap.exists:
        stored_email = _normalize_email((user_snap.to_dict() or {}).get("email_normalized") or (user_snap.to_dict() or {}).get("email"))
        if stored_email and stored_email != email:
            raise SystemExit(f"Safety stop: resolved user email {stored_email!r} does not match requested {email!r}")

    _delete(db, plan)

    verify = _resolve(db, email=email, include_audit=args.include_audit)
    remaining = len(verify["documents"])
    print(json.dumps({
        "deleted": remaining == 0 and verify["user_id"] is None,
        "email": email,
        "former_user_id": plan["user_id"],
        "remaining_document_count": remaining,
        "remaining_user_id": verify["user_id"],
    }, indent=2))
    if remaining or verify["user_id"]:
        print("RESULT cleanup_incomplete")
        return 2
    print("RESULT cleanup_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
