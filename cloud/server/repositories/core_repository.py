import time, uuid, hashlib, secrets
from typing import Optional, Dict
class CoreRepository:
    COLLECTION="core_registrations"
    def __init__(self,db_client): self.db=db_client
    @staticmethod
    def hash_secret(s): return hashlib.sha256(s.encode()).hexdigest()
    def register(self,user_id,core_id=None,core_version=None,machine_hash=None,activation_id=None,entitlement_id=None):
        core_id=str(core_id or uuid.uuid4()); ref=self.db.collection(self.COLLECTION).document(core_id); snap=ref.get(); now=int(time.time())
        if snap.exists:
            d=snap.to_dict() or {}
            if d.get("user_id")!=user_id: raise PermissionError("core_id belongs to another user")
            ref.update({"core_version":core_version or d.get("core_version"),"machine_hash":machine_hash or d.get("machine_hash"),"activation_id":activation_id or d.get("activation_id"),"entitlement_id":entitlement_id or d.get("entitlement_id"),"last_seen_at":now,"updated_at":now}); d=ref.get().to_dict() or {}; d["core_id"]=core_id; return d,None
        secret=secrets.token_urlsafe(32); d={"core_id":core_id,"user_id":user_id,"status":"active","core_version":core_version,"machine_hash":machine_hash,"activation_id":activation_id,"entitlement_id":entitlement_id,"core_secret_hash":self.hash_secret(secret),"registered_at":now,"last_seen_at":now,"created_at":now,"updated_at":now}
        ref.set(d); return d,secret
    def get(self,core_id)->Optional[Dict]:
        s=self.db.collection(self.COLLECTION).document(core_id).get()
        if not s.exists:return None
        d=s.to_dict() or {}; d["core_id"]=core_id; return d
    @classmethod
    def verify_secret_record(cls, record, secret)->bool:
        """Verify a Core credential against an already-loaded registration.

        Heartbeat uses this helper so it does not perform a second Firestore read
        after loading the Core registration for lifecycle/ownership checks.
        """
        import hmac
        if not record or not secret:
            return False
        stored = str(record.get("core_secret_hash") or "")
        candidate = cls.hash_secret(str(secret))
        return bool(stored and hmac.compare_digest(stored, candidate))

    def verify_secret(self,core_id,secret)->bool:
        return self.verify_secret_record(self.get(core_id), secret)

    def reactivate_with_secret(
        self,
        core_id: str,
        *,
        user_id: str,
        machine_hash: str,
        activation_id: str,
        entitlement_id: str,
        core_version=None,
    ):
        """Reactivate a previously deactivated/replaced Core after service proof.

        This repository method does not authorize reactivation by itself. The
        service must call it only after fresh verified-email proof and after an
        activation seat has been reserved for this account/device/Core.
        """
        ref = self.db.collection(self.COLLECTION).document(str(core_id))
        snap = ref.get()
        if not snap.exists:
            raise KeyError("CORE_NOT_FOUND")
        data = snap.to_dict() or {}
        if str(data.get("user_id") or "") != str(user_id):
            raise PermissionError("CORE_OWNERSHIP_CONFLICT")
        if str(data.get("machine_hash") or "") != str(machine_hash or ""):
            raise PermissionError("CORE_RECOVERY_DEVICE_MISMATCH")

        status = str(data.get("status") or "active").lower()
        if status not in {"deactivated", "replaced"}:
            raise RuntimeError("CORE_REACTIVATION_NOT_ALLOWED")

        secret = secrets.token_urlsafe(48)
        now = int(time.time())
        updates = {
            "status": "active",
            "core_version": core_version or data.get("core_version"),
            "activation_id": str(activation_id or ""),
            "entitlement_id": str(entitlement_id or ""),
            "core_secret_hash": self.hash_secret(secret),
            "credential_rotated_at": now,
            "reactivated_at": now,
            "last_seen_at": now,
            "updated_at": now,
            "deactivated_at": None,
            "deactivation_reason": None,
            "replacement_core_id": None,
        }
        ref.update(updates)
        data.update(updates)
        data["core_id"] = str(core_id)
        return data, secret

    def rotate_secret(self, core_id: str, *, user_id: str, machine_hash: str):
        """Rotate Core secret after service-layer recovery authorization."""
        ref = self.db.collection(self.COLLECTION).document(str(core_id))
        snap = ref.get()
        if not snap.exists:
            raise KeyError("CORE_NOT_FOUND")
        data = snap.to_dict() or {}
        if str(data.get("user_id") or "") != str(user_id):
            raise PermissionError("CORE_OWNERSHIP_CONFLICT")
        if str(data.get("machine_hash") or "") != str(machine_hash or ""):
            raise PermissionError("CORE_RECOVERY_DEVICE_MISMATCH")

        secret = secrets.token_urlsafe(48)
        now = int(time.time())
        updates = {
            "core_secret_hash": self.hash_secret(secret),
            "credential_rotated_at": now,
            "last_seen_at": now,
            "updated_at": now,
        }
        ref.update(updates)
        data.update(updates)
        return data, secret


    def mark_replaced(self, core_id: str, *, replacement_core_id: str, reason: str = "seat_transfer"):
        ref = self.db.collection(self.COLLECTION).document(str(core_id))
        snap = ref.get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        now = int(time.time())
        updates = {
            "status": "replaced",
            "replaced_at": now,
            "replacement_core_id": str(replacement_core_id or ""),
            "deactivation_reason": str(reason or "seat_transfer"),
            "updated_at": now,
        }
        ref.update(updates)
        data.update(updates)
        data["core_id"] = str(core_id)
        return data


    def mark_deactivated(self, core_id: str, *, reason: str = "user_deactivate"):
        ref = self.db.collection(self.COLLECTION).document(str(core_id))
        snap = ref.get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        now = int(time.time())
        updates = {
            "status": "deactivated",
            "deactivated_at": now,
            "deactivation_reason": str(reason or "user_deactivate"),
            "updated_at": now,
        }
        ref.update(updates)
        data.update(updates)
        data["core_id"] = str(core_id)
        return data
