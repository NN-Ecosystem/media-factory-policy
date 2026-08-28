from __future__ import annotations

from google.cloud.firestore_v1.base_query import FieldFilter

import hashlib
import time
from typing import Dict, Optional

from google.cloud import firestore


class ActivationRepository:
    COLLECTION = "entitlement_activations"
    RESERVATION_TTL_SECONDS = 300

    def __init__(self, db_client):
        self.db = db_client

    @staticmethod
    def _seat_id(entitlement_id: str, seat_index: int) -> str:
        raw = f"{entitlement_id}:seat:{int(seat_index)}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:40]

    def _ref(self, entitlement_id: str, seat_index: int):
        return self.db.collection(self.COLLECTION).document(
            self._seat_id(entitlement_id, seat_index)
        )

    @staticmethod
    def _public(data: Dict, activation_id: str) -> Dict:
        out = dict(data or {})
        out["activation_id"] = activation_id
        return out

    def get(self, activation_id: str) -> Optional[Dict]:
        snap = self.db.collection(self.COLLECTION).document(str(activation_id)).get()
        if not snap.exists:
            return None
        return self._public(snap.to_dict() or {}, snap.id)

    def import_legacy_machine_bindings(
        self,
        *,
        entitlement: Dict,
        user_id: str,
        machine_hashes,
        now: Optional[int] = None,
    ):
        """Reserve canonical seats for machines already bound to a legacy key."""
        now = int(time.time()) if now is None else int(now)
        entitlement_id = str(entitlement.get("entitlement_id") or "")
        seat_limit = max(1, int(entitlement.get("seat_limit") or 1))
        unique = []
        for value in machine_hashes or []:
            value = str(value or "").strip()
            if value and value not in unique:
                unique.append(value)
        if len(unique) > seat_limit:
            raise RuntimeError("LEGACY_BINDINGS_EXCEED_SEAT_LIMIT")

        imported = []
        for seat_index, machine_hash in enumerate(unique, start=1):
            ref = self._ref(entitlement_id, seat_index)
            snap = ref.get()
            if snap.exists:
                data = snap.to_dict() or {}
                # Idempotent if this seat already represents the same imported machine.
                if (
                    str(data.get("machine_hash") or "") == machine_hash
                    and str(data.get("user_id") or "") == str(user_id)
                ):
                    imported.append(self._public(data, ref.id))
                    continue
                raise RuntimeError("LEGACY_SEAT_IMPORT_CONFLICT")

            data = {
                "activation_id": ref.id,
                "entitlement_id": entitlement_id,
                "user_id": str(user_id),
                "product": str(entitlement.get("product") or "core"),
                "plan": str(entitlement.get("plan") or ""),
                "seat_index": seat_index,
                "seat_limit_snapshot": seat_limit,
                "status": "legacy_reserved",
                "core_id": None,
                "machine_hash": machine_hash,
                "reserved_at": now,
                "reservation_expires_at": None,
                "activated_at": None,
                "last_seen_at": now,
                "deactivated_at": None,
                "migration_source": "legacy_license",
                "created_at": now,
                "lease_generation": 1,
                "lease_expires_at": None,
                "last_heartbeat_at": None,
                "updated_at": now,
            }
            ref.set(data)
            imported.append(data)
        return imported

    def list_for_entitlement(self, entitlement_id: str):
        docs = (
            self.db.collection(self.COLLECTION)
            .where(filter=FieldFilter("entitlement_id", "==", str(entitlement_id)))
            .stream()
        )
        items = []
        for snap in docs:
            items.append(self._public(snap.to_dict() or {}, snap.id))
        items.sort(key=lambda x: int(x.get("seat_index") or 0))
        return items

    def deactivate(
        self,
        activation_id: str,
        *,
        reason: str = "admin_deactivate",
        now: Optional[int] = None,
    ) -> Dict:
        now = int(time.time()) if now is None else int(now)
        ref = self.db.collection(self.COLLECTION).document(str(activation_id))
        snap = ref.get()
        if not snap.exists:
            raise KeyError("ACTIVATION_NOT_FOUND")
        data = snap.to_dict() or {}
        updates = {
            "status": "inactive",
            "deactivated_at": now,
            "deactivation_reason": str(reason or "admin_deactivate"),
            "updated_at": now,
        }
        ref.update(updates)
        data.update(updates)
        return self._public(data, ref.id)

    def active_count_for_entitlement(self, entitlement_id: str) -> int:
        docs = (
            self.db.collection(self.COLLECTION)
            .where(filter=FieldFilter("entitlement_id", "==", str(entitlement_id)))
            .where(filter=FieldFilter("status", "==", "active"))
            .stream()
        )
        return sum(1 for _ in docs)

    def active_for_core(self, core_id: str) -> Optional[Dict]:
        if not core_id:
            return None
        docs = (
            self.db.collection(self.COLLECTION)
            .where(filter=FieldFilter("core_id", "==", str(core_id)))
            .where(filter=FieldFilter("status", "==", "active"))
            .limit(2)
            .stream()
        )
        for snap in docs:
            return self._public(snap.to_dict() or {}, snap.id)
        return None

    def resolve_or_reserve(
        self,
        *,
        entitlement: Dict,
        user_id: str,
        machine_hash: str,
        core_id: str,
        now: Optional[int] = None,
    ) -> Dict:
        now = int(time.time()) if now is None else int(now)
        machine_hash = str(machine_hash or "").strip()
        core_id = str(core_id or "").strip()
        if not machine_hash:
            raise ValueError("MACHINE_BINDING_REQUIRED")
        if not core_id:
            raise ValueError("CORE_ID_REQUIRED")

        entitlement_id = str(entitlement.get("entitlement_id") or "").strip()
        if not entitlement_id:
            raise ValueError("ENTITLEMENT_ID_REQUIRED")

        seat_limit = max(1, int(entitlement.get("seat_limit") or 1))
        refs = [self._ref(entitlement_id, i) for i in range(1, seat_limit + 1)]
        tx = self.db.transaction()

        @firestore.transactional
        def op(transaction):
            snapshots = [ref.get(transaction=transaction) for ref in refs]

            # P35.10: Core identity, not machine identity, owns a Personal Core seat.
            # Multiple Personal Cores may legitimately run on the same physical PC,
            # therefore machine_hash must never collapse two distinct core_id values
            # onto one active seat. Reuse only the exact Core binding. A legacy
            # reservation without core_id may still be claimed by the same machine
            # during migration.
            for snap in snapshots:
                if not snap.exists:
                    continue
                data = snap.to_dict() or {}
                status = str(data.get("status") or "")
                reservation_expires_at = int(data.get("reservation_expires_at") or 0)
                live = status in ("active", "legacy_reserved") or (
                    status == "reserved" and reservation_expires_at > now
                )
                same_user = str(data.get("user_id") or "") == str(user_id)
                existing_core_id = str(data.get("core_id") or "")
                exact_core = bool(existing_core_id and existing_core_id == core_id)
                legacy_claim = (
                    status == "legacy_reserved"
                    and not existing_core_id
                    and str(data.get("machine_hash") or "") == machine_hash
                )
                if live and same_user and (exact_core or legacy_claim):
                    updates = {}
                    if legacy_claim:
                        updates["core_id"] = core_id
                        data["core_id"] = core_id
                    if status == "legacy_reserved":
                        updates.update({
                            "status": "reserved",
                            "reserved_at": now,
                            "reservation_expires_at": now + self.RESERVATION_TTL_SECONDS,
                            "migration_source": "legacy_license",
                        })
                        data.update(updates)
                    if updates:
                        updates["updated_at"] = now
                        transaction.update(snap.reference, updates)
                    return self._public(data, snap.id)

            # Allocate only an empty/inactive/revoked/expired-reservation seat.
            for seat_index, snap in enumerate(snapshots, start=1):
                available = not snap.exists
                if snap.exists:
                    data = snap.to_dict() or {}
                    status = str(data.get("status") or "")
                    reservation_expires_at = int(data.get("reservation_expires_at") or 0)
                    available = (
                        status in ("inactive", "revoked")
                        or (status == "reserved" and reservation_expires_at <= now)
                    )
                if not available:
                    continue

                ref = refs[seat_index - 1]
                data = {
                    "activation_id": ref.id,
                    "entitlement_id": entitlement_id,
                    "user_id": str(user_id),
                    "product": str(entitlement.get("product") or "core"),
                    "plan": str(entitlement.get("plan") or ""),
                    "seat_index": seat_index,
                    "seat_limit_snapshot": seat_limit,
                    "status": "reserved",
                    "core_id": core_id,
                    "machine_hash": machine_hash,
                    "reserved_at": now,
                    "reservation_expires_at": now + self.RESERVATION_TTL_SECONDS,
                    "activated_at": None,
                    "last_seen_at": now,
                    "deactivated_at": None,
                    "created_at": now,
                    "lease_generation": 1,
                    "lease_expires_at": None,
                    "last_heartbeat_at": None,
                    "updated_at": now,
                }
                transaction.set(ref, data)
                return data

            raise RuntimeError("ACTIVATION_SEAT_LIMIT_REACHED")

        return op(tx)

    def transfer_single_seat(
        self,
        *,
        entitlement: Dict,
        user_id: str,
        machine_hash: str,
        core_id: str,
        now: Optional[int] = None,
    ) -> Dict:
        """Transfer the canonical one-seat activation after service-layer proof."""
        now = int(time.time()) if now is None else int(now)
        entitlement_id = str(entitlement.get("entitlement_id") or "").strip()
        seat_limit = max(1, int(entitlement.get("seat_limit") or 1))
        if not entitlement_id:
            raise ValueError("ENTITLEMENT_ID_REQUIRED")
        if seat_limit != 1:
            raise RuntimeError("ACTIVATION_TRANSFER_REQUIRES_SEAT_SELECTION")
        if not str(machine_hash or "").strip():
            raise ValueError("MACHINE_BINDING_REQUIRED")
        if not str(core_id or "").strip():
            raise ValueError("CORE_ID_REQUIRED")

        ref = self._ref(entitlement_id, 1)
        tx = self.db.transaction()

        @firestore.transactional
        def op(transaction):
            snap = ref.get(transaction=transaction)
            if not snap.exists:
                raise RuntimeError("ACTIVATION_TRANSFER_SOURCE_NOT_FOUND")
            data = snap.to_dict() or {}
            if str(data.get("user_id") or "") != str(user_id):
                raise PermissionError("ACTIVATION_OWNERSHIP_CONFLICT")

            previous_core_id = str(data.get("core_id") or "")
            previous_machine_hash = str(data.get("machine_hash") or "")
            previous_generation = max(1, int(data.get("lease_generation") or 1))
            updates = {
                "status": "reserved",
                "core_id": str(core_id),
                "machine_hash": str(machine_hash),
                "reserved_at": now,
                "reservation_expires_at": now + self.RESERVATION_TTL_SECONDS,
                "activated_at": None,
                "last_seen_at": now,
                "deactivated_at": None,
                "deactivation_reason": None,
                "transfer_from_core_id": previous_core_id or None,
                "transfer_from_machine_hash": previous_machine_hash or None,
                "transferred_at": now,
                "lease_generation": previous_generation + 1,
                "lease_expires_at": None,
                "last_heartbeat_at": None,
                "updated_at": now,
            }
            transaction.update(ref, updates)
            data.update(updates)
            data["previous_core_id"] = previous_core_id or None
            data["previous_machine_hash"] = previous_machine_hash or None
            return self._public(data, ref.id)

        return op(tx)

    def activate(
        self,
        activation_id: str,
        *,
        user_id: str,
        entitlement_id: str,
        core_id: str,
        machine_hash: str,
        now: Optional[int] = None,
    ) -> Dict:
        now = int(time.time()) if now is None else int(now)
        ref = self.db.collection(self.COLLECTION).document(str(activation_id))
        tx = self.db.transaction()

        @firestore.transactional
        def op(transaction):
            snap = ref.get(transaction=transaction)
            if not snap.exists:
                raise RuntimeError("ACTIVATION_NOT_FOUND")
            data = snap.to_dict() or {}
            if str(data.get("user_id") or "") != str(user_id):
                raise PermissionError("ACTIVATION_OWNERSHIP_CONFLICT")
            if str(data.get("entitlement_id") or "") != str(entitlement_id):
                raise PermissionError("ACTIVATION_ENTITLEMENT_CONFLICT")
            if str(data.get("machine_hash") or "") != str(machine_hash or ""):
                raise PermissionError("ACTIVATION_DEVICE_CONFLICT")
            existing_core = str(data.get("core_id") or "")
            if existing_core and existing_core != str(core_id):
                raise PermissionError("ACTIVATION_CORE_CONFLICT")

            updates = {
                "status": "active",
                "core_id": str(core_id),
                "activated_at": int(data.get("activated_at") or now),
                "last_seen_at": now,
                "reservation_expires_at": None,
                "lease_generation": max(1, int(data.get("lease_generation") or 1)),
                "lease_expires_at": None,
                "last_heartbeat_at": None,
                "updated_at": now,
            }
            transaction.update(ref, updates)
            data.update(updates)
            return self._public(data, ref.id)

        return op(tx)

    def require_same_device_binding(
        self,
        *,
        activation_id: str,
        user_id: str,
        entitlement_id: str,
        machine_hash: str,
        core_id: str,
    ) -> Dict:
        """Authorize credential recovery only for the existing active seat binding."""
        activation = self.get(activation_id)
        if not activation or str(activation.get("status") or "") != "active":
            raise PermissionError("ACTIVATION_RECOVERY_NOT_ACTIVE")
        if str(activation.get("user_id") or "") != str(user_id):
            raise PermissionError("ACTIVATION_RECOVERY_ACCOUNT_MISMATCH")
        if str(activation.get("entitlement_id") or "") != str(entitlement_id):
            raise PermissionError("ACTIVATION_RECOVERY_ENTITLEMENT_MISMATCH")
        if str(activation.get("machine_hash") or "") != str(machine_hash or ""):
            raise PermissionError("ACTIVATION_RECOVERY_DEVICE_MISMATCH")
        if str(activation.get("core_id") or "") != str(core_id or ""):
            raise PermissionError("ACTIVATION_RECOVERY_CORE_MISMATCH")
        return activation


    @staticmethod
    def validate_heartbeat_record(
        activation: Dict,
        *,
        user_id: str,
        core_id: str,
        expected_generation: Optional[int] = None,
    ) -> Dict:
        data = dict(activation or {})
        if not data or str(data.get("status") or "") != "active":
            raise PermissionError("SEAT_REVOKED")
        if str(data.get("user_id") or "") != str(user_id):
            raise PermissionError("SEAT_REVOKED")
        if str(data.get("core_id") or "") != str(core_id):
            raise PermissionError("SEAT_REVOKED")
        generation = max(1, int(data.get("lease_generation") or 1))
        if expected_generation is not None and int(expected_generation) != generation:
            raise PermissionError("SEAT_GENERATION_STALE")
        data["lease_generation"] = generation
        return data

    @staticmethod
    def telemetry_due(
        activation: Dict,
        *,
        now: int,
        write_interval_seconds: int,
    ) -> bool:
        last = int((activation or {}).get("last_heartbeat_at") or 0)
        return last <= 0 or int(now) - last >= max(300, int(write_interval_seconds or 900))


    def heartbeat(
        self,
        *,
        activation_id: str,
        user_id: str,
        core_id: str,
        lease_seconds: int = 180,
        expected_generation: Optional[int] = None,
        now: Optional[int] = None,
    ) -> Dict:
        """Renew the online seat lease only for the current active Core binding."""
        now = int(time.time()) if now is None else int(now)
        lease_seconds = max(300, min(int(lease_seconds or 1200), 3600))
        ref = self.db.collection(self.COLLECTION).document(str(activation_id))
        tx = self.db.transaction()

        @firestore.transactional
        def op(transaction):
            snap = ref.get(transaction=transaction)
            if not snap.exists:
                raise PermissionError("SEAT_REVOKED")
            data = snap.to_dict() or {}
            if str(data.get("status") or "") != "active":
                raise PermissionError("SEAT_REVOKED")
            if str(data.get("user_id") or "") != str(user_id):
                raise PermissionError("SEAT_REVOKED")
            if str(data.get("core_id") or "") != str(core_id):
                raise PermissionError("SEAT_REVOKED")
            generation = max(1, int(data.get("lease_generation") or 1))
            if expected_generation is not None and int(expected_generation) != generation:
                raise PermissionError("SEAT_GENERATION_STALE")

            updates = {
                "last_seen_at": now,
                "last_heartbeat_at": now,
                "lease_expires_at": now + lease_seconds,
                "updated_at": now,
            }
            transaction.update(ref, updates)
            data.update(updates)
            data["lease_generation"] = generation
            return self._public(data, ref.id)

        return op(tx)

    def touch(self, activation_id: str, now: Optional[int] = None) -> None:
        now = int(time.time()) if now is None else int(now)
        self.db.collection(self.COLLECTION).document(str(activation_id)).update({
            "last_seen_at": now,
            "updated_at": now,
        })
