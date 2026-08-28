import os
import time
import secrets
import uuid

from server.services.cloud_errors import CloudFoundationError
from server.services.cloud_access_policy import canonical_plan


class CloudFoundationService:
    def __init__(
        self,
        users,
        verifications,
        trials,
        entitlements,
        cores,
        activations,
        legacy_licenses,
        signer,
        email_delivery=None,
        audit=None,
        trial_days=14,
        grant_ttl=43200,
        access_policy=None,
        onboarding_sessions=None,
        onboarding_ttl=86400,
    ):
        self.users = users
        self.verifications = verifications
        self.trials = trials
        self.entitlements = entitlements
        self.cores = cores
        self.activations = activations
        self.legacy_licenses = legacy_licenses
        self.signer = signer
        self.email_delivery = email_delivery
        self.audit = audit
        self.trial_days = int(trial_days)
        self.grant_ttl = int(grant_ttl)
        self.access_policy = access_policy
        self.onboarding_sessions = onboarding_sessions
        self.onboarding_ttl = int(onboarding_ttl)

    def _audit(self, event_type, **kwargs):
        if self.audit is None:
            return
        try:
            self.audit.record(event_type, **kwargs)
        except Exception:
            # Access decisions must never fail because audit persistence is unavailable.
            pass

    def _classify_account_activation(self, user, now=None):
        now = int(time.time()) if now is None else int(now)
        if not bool(user.get("email_verified_at")):
            return {"account_state":"new_or_unverified","activation_class":"trial","entitlement":None}
        ents=[e for e in self.entitlements.active_for_user(user["user_id"],now) if e.get("product")=="core"]
        priority={"payment":50,"manual":40,"legacy_license":30,"promo":20,"trial":10}
        ents.sort(key=lambda e:(priority.get(str(e.get("source_type") or ""),0),int(e.get("expires_at") or 2**31)),reverse=True)
        best=ents[0] if ents else None
        if best and str(best.get("source_type") or "") != "trial": return {"account_state":"existing_licensed","activation_class":"license","entitlement":best}
        if best: return {"account_state":"existing_trial","activation_class":"trial_existing","entitlement":best}
        return {"account_state":"existing_verified_no_entitlement","activation_class":"existing_account","entitlement":None}

    def register(self, email, *, deliver_email=True):
        u = self.users.create_or_get(email)
        account_already_verified = bool(u.get("email_verified_at"))
        classification = self._classify_account_activation(u)
        activation_class = str(classification.get("activation_class") or "")
        purpose = "trial_verification" if not account_already_verified else ("license_recovery" if activation_class == "license" else "core_activation")

        # Only one live challenge per account/purpose. Older pending challenges
        # become non-authoritative before a new one is issued.
        if hasattr(self.verifications, "supersede_other_live"):
            self.verifications.supersede_other_live(u["user_id"], purpose)

        token = secrets.token_urlsafe(32)
        try:
            v = self.verifications.create(
                u["user_id"], u["email"], token, purpose=purpose
            )
        except TypeError:
            v = self.verifications.create(u["user_id"], u["email"], token)
            if isinstance(v, dict):
                v.setdefault("purpose", purpose)
        onboarding_record = None
        onboarding_secret = None
        if self.onboarding_sessions is not None:
            onboarding_record, onboarding_secret = self.onboarding_sessions.create(
                u["user_id"], u["email"], v["verification_id"], self.onboarding_ttl
            )
            if hasattr(self.onboarding_sessions, "supersede_other_live"):
                self.onboarding_sessions.supersede_other_live(
                    u["user_id"], onboarding_record["session_id"]
                )
        if deliver_email and self.email_delivery is not None:
            try:
                self.email_delivery.send_verification(
                    email=u["email"], token=token, expires_at=v["expires_at"], purpose=purpose
                )
            except TypeError:
                # Compatibility with older test/custom adapters.
                self.email_delivery.send_verification(
                    email=u["email"], token=token, expires_at=v["expires_at"]
                )
        self._audit(
            "cloud.user.registered",
            actor_type="user",
            actor_id=u["user_id"],
            subject_type="user",
            subject_id=u["user_id"],
            metadata={"verification_id": v["verification_id"], "purpose": purpose},
        )
        result = {
            "user_id": u["user_id"],
            "email": u["email"],
            "status": "activation_confirmation_required" if account_already_verified else u.get("status"),
            # Backward-compatible field: account email verification is only required
            # for a never-verified account. Fresh installations still require an
            # activation confirmation challenge to prove control of an existing email.
            "verification_required": not account_already_verified,
            "activation_confirmation_required": True,
            "account_state": classification.get("account_state"),
            "activation_class": activation_class,
            "effective_entitlement": classification.get("entitlement"),
            "verification_purpose": purpose,
            "trial_activation_required": purpose == "trial_verification",
            "verification_expires_at": v["expires_at"],
        }
        if onboarding_record is not None and onboarding_secret is not None:
            result.update({
                "onboarding_session_id": onboarding_record["session_id"],
                "onboarding_secret": onboarding_secret,
                "onboarding_expires_at": onboarding_record["expires_at"],
            })
        if os.getenv("CLOUD_DEV_EXPOSE_VERIFICATION_TOKEN", "false").lower() == "true":
            result["verification_token"] = token
        return result, token

    def verify_email(self, token):
        now = int(time.time())
        v = self.verifications.find_by_token(str(token or ""))
        if not v:
            self._audit("cloud.email.verify_rejected", outcome="denied", metadata={"reason": "invalid_token"})
            raise CloudFoundationError("VERIFICATION_TOKEN_INVALID", "Invalid verification token.", 400)
        if v.get("status") == "verified":
            self._audit(
                "cloud.email.verify_rejected",
                actor_type="user",
                actor_id=v.get("user_id"),
                subject_type="verification",
                subject_id=v.get("verification_id"),
                outcome="denied",
                metadata={"reason": "already_used"},
            )
            raise CloudFoundationError("VERIFICATION_ALREADY_USED", "Verification token already used.", 409)
        if int(v.get("expires_at", 0)) <= now:
            raise CloudFoundationError("VERIFICATION_TOKEN_EXPIRED", "Verification token expired.", 410)
        user = self.users.get(v["user_id"])
        if not user:
            raise CloudFoundationError("USER_NOT_FOUND", "User not found.", 404)

        account_was_verified = bool(user.get("email_verified_at"))
        verified_at = int(user.get("email_verified_at") or now)
        if not user.get("email_verified_at"):
            self.users.mark_verified(v["user_id"], verified_at)
        self.verifications.mark_verified(v["verification_id"], now)
        purpose = str(v.get("purpose") or ("core_activation" if account_was_verified else "trial_verification"))
        trial = None
        ent = None
        if purpose == "trial_verification":
            trial = self.trials.activate_once(v["user_id"], verified_at, self.trial_days)
            ent = self.entitlements.issue_once(
                v["user_id"],
                "core",
                "trial",
                "trial",
                trial["trial_id"],
                trial["started_at"],
                None,  # Trial is quota-limited and has no entitlement expiry.
                seat_limit=1,
                activation_policy={
                    "binding": "machine_core",
                    "transfer": "admin_only",
                },
            )
        else:
            try: ent = self._select_core_entitlement(v["user_id"], now)
            except CloudFoundationError: ent = None
        self._audit(
            "cloud.email.verified",
            actor_type="user",
            actor_id=v["user_id"],
            subject_type="user",
            subject_id=v["user_id"],
            metadata={
                "verification_id": v["verification_id"],
                "trial_id": (trial or {}).get("trial_id"),
                "entitlement_id": (ent or {}).get("entitlement_id"),
                "verification_purpose": purpose,
            },
        )
        return {
            "user_id": v["user_id"],
            "email_verified_at": verified_at,
            "account_was_verified": account_was_verified,
            "verification_purpose": purpose,
            "activation_class": "trial" if purpose == "trial_verification" else ("license" if ent and str(ent.get("source_type") or "") != "trial" else "existing_account"),
            "trial": trial,
            "entitlement": ent,
        }

    def _require_onboarding_session(self, session_id, secret):
        if self.onboarding_sessions is None:
            raise CloudFoundationError("ONBOARDING_UNAVAILABLE", "Cloud onboarding is unavailable.", 503)
        session = self.onboarding_sessions.verify(str(session_id or ""), str(secret or ""))
        if not session:
            raise CloudFoundationError("ONBOARDING_CREDENTIAL_INVALID", "Onboarding credential invalid.", 403)
        if int(session.get("expires_at") or 0) <= int(time.time()):
            raise CloudFoundationError("ONBOARDING_SESSION_EXPIRED", "Onboarding session expired.", 410)
        return session

    def onboarding_status(self, session_id, secret):
        session = self._require_onboarding_session(session_id, secret)
        user = self.users.get(session["user_id"])
        if not user:
            raise CloudFoundationError("USER_NOT_FOUND", "User not found.", 404)
        proof = self.verifications.get(session.get("verification_id"))
        verified = bool(proof and proof.get("status") == "verified")
        purpose = str((proof or {}).get("purpose") or "trial_verification")
        if verified:
            state = "activation_confirmed" if purpose == "core_activation" else "email_verified"
        else:
            state = "pending_activation_confirmation" if purpose == "core_activation" else "pending_verification"
        if session.get("status") == "completed":
            state = "completed"
        elif verified and self.onboarding_sessions is not None:
            self.onboarding_sessions.update_status(session["session_id"], "email_verified")
        trial = self.trials.get(session["user_id"]) if verified else None
        ents = self.entitlements.active_for_user(session["user_id"]) if verified else []
        return {
            "schema": "core_cloud_onboarding_status_v1",
            "state": state,
            "user_id": session["user_id"],
            "email": session.get("email"),
            "email_verified": bool(user.get("email_verified_at")),
            "activation_confirmed": verified,
            "verification_purpose": purpose,
            "email_verified_at": user.get("email_verified_at"),
            "trial": trial,
            "active_entitlements": ents,
            "core_id": session.get("core_id"),
        }

    def resend_verification(self, session_id, secret):
        session = self._require_onboarding_session(session_id, secret)
        user = self.users.get(session["user_id"])
        if not user:
            raise CloudFoundationError("USER_NOT_FOUND", "User not found.", 404)
        current_proof = self.verifications.get(session.get("verification_id"))
        current_purpose = str((current_proof or {}).get("purpose") or "")
        if current_proof and current_proof.get("status") == "verified":
            return {
                "sent": False,
                "already_verified": bool(user.get("email_verified_at")),
                "already_confirmed": True,
                "verification_purpose": current_purpose or ("core_activation" if user.get("email_verified_at") else "trial_verification"),
            }
        purpose = "core_activation" if user.get("email_verified_at") else "trial_verification"
        token = secrets.token_urlsafe(32)
        try:
            v = self.verifications.create(user["user_id"], user["email"], token, purpose=purpose)
        except TypeError:
            v = self.verifications.create(user["user_id"], user["email"], token)
            if isinstance(v, dict):
                v.setdefault("purpose", purpose)
        if self.email_delivery is not None:
            try:
                self.email_delivery.send_verification(
                    email=user["email"], token=token, expires_at=v["expires_at"], purpose=purpose
                )
            except TypeError:
                self.email_delivery.send_verification(email=user["email"], token=token, expires_at=v["expires_at"])
        self.onboarding_sessions.set_verification(session["session_id"], v["verification_id"])
        self._audit(
            "cloud.email.verification_resent",
            actor_type="user", actor_id=user["user_id"],
            subject_type="verification", subject_id=v["verification_id"],
        )
        return {"sent": True, "verification_expires_at": v["expires_at"], "verification_purpose": purpose}

    def _select_core_entitlement(self, user_id, now=None, *, machine_hash=None):
        """Select one effective Core entitlement for release authority.

        Priority for current release:
        1) legacy_license
        2) manual
        3) trial
        Full License always beats Trial.

        When machine_hash is provided, prefer an entitlement whose activation can
        either reuse the same machine or has an available seat.
        """
        now = int(time.time()) if now is None else int(now)
        core_ents = [
            e for e in self.entitlements.active_for_user(user_id, now)
            if e.get("product") == "core"
        ]
        if not core_ents:
            raise CloudFoundationError(
                "ENTITLEMENT_INACTIVE",
                "Active Core entitlement required.",
                403,
            )

        # Current release authority order.
        # Keep entitlement authority order identical to CloudAccessPolicy so
        # activation, seat binding, signed grant, and effective access cannot
        # select different entitlements.
        source_priority = {
            "payment": 500,
            "manual": 400,
            "legacy_license": 300,
            "promo": 200,
            "trial": 100,
        }

        def seat_rank(entitlement):
            if not machine_hash:
                return 0
            seats = self.activations.list_for_entitlement(
                entitlement["entitlement_id"]
            )
            # Best: same machine already owns/reserves a seat.
            for seat in seats:
                if (
                    str(seat.get("machine_hash") or "") == str(machine_hash)
                    and str(seat.get("status") or "")
                    in ("active", "reserved", "legacy_reserved")
                ):
                    return 2
            active_like = sum(
                1
                for seat in seats
                if str(seat.get("status") or "")
                in ("active", "reserved", "legacy_reserved")
            )
            seat_limit = max(1, int(entitlement.get("seat_limit") or 1))
            return 1 if active_like < seat_limit else -1

        ranked = []
        for ent in core_ents:
            source = str(ent.get("source_type") or "")
            rank = source_priority.get(source, 0)
            seat_state = seat_rank(ent)
            ranked.append((rank, seat_state, int(ent.get("expires_at") or 2**31), ent))

        # First by authority class, then by reusable/free seat, then later expiry.
        ranked.sort(
            key=lambda item: (item[0], item[1], item[2]),
            reverse=True,
        )

        selected = ranked[0][3]

        # A lower-priority Trial/manual entitlement must never replace a higher
        # priority Full License merely because the lower one already has a seat.
        return selected


    def _reserve_activation(self, user_id, entitlement, machine_hash, core_id):
        if not str(machine_hash or "").strip():
            raise CloudFoundationError(
                "MACHINE_BINDING_REQUIRED",
                "Machine binding is required for Core activation.",
                400,
            )
        try:
            return self.activations.resolve_or_reserve(
                entitlement=entitlement,
                user_id=user_id,
                machine_hash=machine_hash,
                core_id=core_id,
            )
        except ValueError as exc:
            raise CloudFoundationError(str(exc), "Invalid activation binding.", 400) from exc
        except RuntimeError as exc:
            if str(exc) == "ACTIVATION_SEAT_LIMIT_REACHED":
                self._audit(
                    "cloud.activation.rejected",
                    actor_type="user",
                    actor_id=user_id,
                    outcome="denied",
                    metadata={
                        "reason": "seat_limit_reached",
                        "entitlement_id": entitlement.get("entitlement_id"),
                        "seat_limit": int(entitlement.get("seat_limit") or 1),
                    },
                )
                raise CloudFoundationError(
                    "ACTIVATION_SEAT_LIMIT_REACHED",
                    "This account has no available Core activation seats.",
                    409,
                ) from exc
            raise

    def _activate_binding(self, activation, *, user_id, entitlement, core_id, machine_hash):
        try:
            return self.activations.activate(
                activation["activation_id"],
                user_id=user_id,
                entitlement_id=entitlement["entitlement_id"],
                core_id=core_id,
                machine_hash=machine_hash,
            )
        except PermissionError as exc:
            raise CloudFoundationError(
                str(exc), "Core activation binding conflict.", 409
            ) from exc
        except RuntimeError as exc:
            raise CloudFoundationError(
                str(exc), "Core activation is unavailable.", 409
            ) from exc

    def _activation_for_core_record(self, core):
        """Resolve the exact activation owned by a Core registration.

        P35.10 invariant: core_registrations.activation_id is canonical.  Falling
        back to a query by core_id is allowed only for legacy registrations that
        predate activation_id persistence.  This prevents stale/duplicate seat
        history from making heartbeat, grant, or deactivate operate on another
        Personal Core seat.
        """
        if not core:
            return None
        core_id = str(core.get("core_id") or "")
        activation_id = str(core.get("activation_id") or "")
        if activation_id:
            activation = self.activations.get(activation_id)
            if not activation:
                return None
            if str(activation.get("core_id") or "") != core_id:
                raise CloudFoundationError(
                    "ACTIVATION_BINDING_CONFLICT",
                    "Core registration activation binding is inconsistent.",
                    403,
                )
            return activation if str(activation.get("status") or "") == "active" else None
        return self.activations.active_for_core(core_id)

    def _recover_same_device_core(
        self,
        *,
        user_id,
        entitlement,
        core,
        machine_hash,
    ):
        """Rotate credential for an already-bound Core on the same machine."""
        if not core:
            raise CloudFoundationError(
                "CORE_REGISTRATION_INVALID", "Core registration invalid.", 403
            )
        if str(core.get("user_id") or "") != str(user_id):
            raise CloudFoundationError(
                "CORE_OWNERSHIP_CONFLICT", "Core belongs to another account.", 403
            )
        if str(core.get("machine_hash") or "") != str(machine_hash or ""):
            raise CloudFoundationError(
                "CORE_RECOVERY_DEVICE_MISMATCH",
                "Credential recovery is allowed only from the bound machine.",
                403,
            )

        activation = self._activation_for_core_record(core)
        activation_id = str((activation or {}).get("activation_id") or "")
        if not activation_id:
            raise CloudFoundationError(
                "ACTIVATION_RECOVERY_NOT_FOUND",
                "No active Core activation is available for recovery.",
                409,
            )

        try:
            activation = self.activations.require_same_device_binding(
                activation_id=activation_id,
                user_id=user_id,
                entitlement_id=entitlement["entitlement_id"],
                machine_hash=machine_hash,
                core_id=core["core_id"],
            )
        except PermissionError as exc:
            raise CloudFoundationError(
                str(exc),
                "Core activation does not match this account/device.",
                403,
            ) from exc

        try:
            core, core_secret = self.cores.rotate_secret(
                core["core_id"],
                user_id=user_id,
                machine_hash=machine_hash,
            )
        except KeyError as exc:
            raise CloudFoundationError("CORE_NOT_FOUND", "Registered Core not found.", 404) from exc
        except PermissionError as exc:
            raise CloudFoundationError(str(exc), "Core credential recovery denied.", 403) from exc

        self.activations.touch(activation["activation_id"])
        grant = self.issue_grant(user_id, core["core_id"], core_secret)
        self._audit(
            "cloud.core.credential_rotated",
            actor_type="user",
            actor_id=user_id,
            subject_type="core",
            subject_id=core["core_id"],
            metadata={"activation_id": activation["activation_id"], "reason": "same_device_recovery"},
        )
        public_core = {k: v for k, v in core.items() if k != "core_secret_hash"}
        public_core["core_secret"] = core_secret
        return public_core, grant

    def _reserve_after_verified_confirmation(
        self, *, user_id, entitlement, machine_hash, candidate_core_id, proof
    ):
        """Reserve normally, or move a one-seat entitlement after fresh email proof."""
        try:
            return self._reserve_activation(
                user_id, entitlement, machine_hash, candidate_core_id
            ), None
        except CloudFoundationError as exc:
            if str(getattr(exc, "code", "") or "") != "ACTIVATION_SEAT_LIMIT_REACHED":
                raise

            purpose = str((proof or {}).get("purpose") or "")
            verified = str((proof or {}).get("status") or "") == "verified"
            seat_limit = max(1, int(entitlement.get("seat_limit") or 1))
            if not verified or purpose not in {"core_activation", "license_recovery"}:
                raise
            if seat_limit != 1:
                raise

            moved = self.activations.transfer_single_seat(
                entitlement=entitlement,
                user_id=user_id,
                machine_hash=machine_hash,
                core_id=candidate_core_id,
            )
            previous_core_id = str(moved.get("previous_core_id") or "")
            self._audit(
                "cloud.activation.transferred",
                actor_type="user",
                actor_id=user_id,
                subject_type="activation",
                subject_id=moved.get("activation_id"),
                metadata={
                    "entitlement_id": entitlement.get("entitlement_id"),
                    "previous_core_id": previous_core_id or None,
                    "replacement_core_id": candidate_core_id,
                    "proof_purpose": purpose,
                },
            )
            return moved, previous_core_id or None

    def complete_onboarding(self, session_id, secret, core_id=None, core_version=None, machine_hash=None):
        session = self._require_onboarding_session(session_id, secret)
        user_id = session["user_id"]
        proof = self.verifications.get(session.get("verification_id"))
        if not proof or proof.get("status") != "verified":
            raise CloudFoundationError("EMAIL_NOT_VERIFIED", "Verify this activation email before activating Core.", 403)
        user = self.users.get(user_id)
        if not user or not user.get("email_verified_at") or user.get("status") != "active":
            raise CloudFoundationError("ACCOUNT_NOT_ACTIVE", "Verified active account required.", 403)
        entitlement = self._select_core_entitlement(user_id, machine_hash=machine_hash)
        if session.get("status") == "completed" and session.get("core_id"):
            core = self.cores.get(session["core_id"])
            public_core, grant = self._recover_same_device_core(
                user_id=user_id,
                entitlement=entitlement,
                core=core,
                machine_hash=machine_hash,
            )
            return {
                "schema": "core_cloud_onboarding_complete_v1",
                "completed": True,
                "reconnected": True,
                "credential_rotated": True,
                "core": public_core,
                "access_grant": grant,
            }
        candidate_core_id = str(core_id or uuid.uuid4())
        activation, previous_core_id = self._reserve_after_verified_confirmation(
            user_id=user_id,
            entitlement=entitlement,
            machine_hash=machine_hash,
            candidate_core_id=candidate_core_id,
            proof=proof,
        )
        resolved_core_id = str(activation.get("core_id") or candidate_core_id)
        existing_core = self.cores.get(resolved_core_id)
        try:
            if existing_core and str(existing_core.get("status") or "active").lower() in {"deactivated", "replaced"}:
                # Fresh verified-email proof plus a newly reserved seat authorizes
                # reactivation of this exact account/device/Core. Rotate the
                # credential; never revive a Core from email identity alone.
                core, core_secret = self.cores.reactivate_with_secret(
                    resolved_core_id,
                    user_id=user_id,
                    machine_hash=machine_hash,
                    activation_id=activation["activation_id"],
                    entitlement_id=entitlement["entitlement_id"],
                    core_version=core_version,
                )
            else:
                core, core_secret = self.cores.register(
                    user_id,
                    resolved_core_id,
                    core_version,
                    machine_hash,
                    activation_id=activation["activation_id"],
                    entitlement_id=entitlement["entitlement_id"],
                )
        except PermissionError as exc:
            code = str(exc) or "CORE_OWNERSHIP_CONFLICT"
            if code == "CORE_RECOVERY_DEVICE_MISMATCH":
                raise CloudFoundationError(code, "Core reactivation device mismatch.", 403) from exc
            raise CloudFoundationError("CORE_OWNERSHIP_CONFLICT", "Core ID belongs to another user.", 403) from exc
        except (KeyError, RuntimeError) as exc:
            raise CloudFoundationError(str(exc), "Core reactivation failed.", 409) from exc
        if not core_secret:
            public_core, grant = self._recover_same_device_core(
                user_id=user_id,
                entitlement=entitlement,
                core=core,
                machine_hash=machine_hash,
            )
            self.onboarding_sessions.mark_completed(session["session_id"], core["core_id"])
            if hasattr(self.onboarding_sessions, "supersede_other_live"):
                self.onboarding_sessions.supersede_other_live(user_id, session["session_id"])
            if hasattr(self.verifications, "supersede_other_live"):
                self.verifications.supersede_other_live(
                    user_id, str(proof.get("purpose") or ""), proof.get("verification_id")
                )
            return {
                "schema": "core_cloud_onboarding_complete_v1",
                "completed": True,
                "reconnected": True,
                "credential_rotated": True,
                "core": public_core,
                "access_grant": grant,
            }
        activation = self._activate_binding(
            activation,
            user_id=user_id,
            entitlement=entitlement,
            core_id=core["core_id"],
            machine_hash=machine_hash,
        )
        if previous_core_id and previous_core_id != core["core_id"]:
            try:
                self.cores.mark_replaced(
                    previous_core_id,
                    replacement_core_id=core["core_id"],
                    reason="verified_email_seat_transfer",
                )
            except Exception:
                pass
        grant = self.issue_grant(user_id, core["core_id"], core_secret)
        self.onboarding_sessions.mark_completed(session["session_id"], core["core_id"])
        if hasattr(self.onboarding_sessions, "supersede_other_live"):
            self.onboarding_sessions.supersede_other_live(user_id, session["session_id"])
        if hasattr(self.verifications, "supersede_other_live"):
            self.verifications.supersede_other_live(
                user_id, str(proof.get("purpose") or ""), proof.get("verification_id")
            )
        public_core = {k: v for k, v in core.items() if k != "core_secret_hash"}
        public_core["core_secret"] = core_secret
        self._audit(
            "cloud.onboarding.completed", actor_type="user", actor_id=user_id,
            subject_type="core", subject_id=core["core_id"],
        )
        return {
            "schema": "core_cloud_onboarding_complete_v1",
            "completed": True,
            "reconnected": False,
            "seat_transferred": bool(previous_core_id),
            "previous_core_id": previous_core_id,
            "core": public_core,
            "access_grant": grant,
        }

    def register_core(self, user_id, verification_token, core_id=None, core_version=None, machine_hash=None):
        proof = self.verifications.find_by_token(str(verification_token or ""))
        if not proof or proof.get("user_id") != user_id or proof.get("status") != "verified":
            self._audit(
                "cloud.core.registration_rejected",
                actor_type="user",
                actor_id=user_id,
                outcome="denied",
                metadata={"reason": "verified_email_proof_required"},
            )
            raise CloudFoundationError("VERIFIED_EMAIL_PROOF_REQUIRED", "Verified email proof required.", 403)
        u = self.users.get(user_id)
        if not u or not u.get("email_verified_at") or u.get("status") != "active":
            raise CloudFoundationError("ACCOUNT_NOT_ACTIVE", "Verified active account required.", 403)
        entitlement = self._select_core_entitlement(user_id, machine_hash=machine_hash)
        candidate_core_id = str(core_id or uuid.uuid4())
        activation = self._reserve_activation(
            user_id, entitlement, machine_hash, candidate_core_id
        )
        resolved_core_id = str(activation.get("core_id") or candidate_core_id)
        try:
            core, secret = self.cores.register(
                user_id,
                resolved_core_id,
                core_version,
                machine_hash,
                activation_id=activation["activation_id"],
                entitlement_id=entitlement["entitlement_id"],
            )
        except PermissionError:
            raise CloudFoundationError("CORE_OWNERSHIP_CONFLICT", "Core ID belongs to another user.", 403)
        activation = self._activate_binding(
            activation,
            user_id=user_id,
            entitlement=entitlement,
            core_id=core["core_id"],
            machine_hash=machine_hash,
        )
        public = {k: v for k, v in core.items() if k != "core_secret_hash"}
        if secret:
            public["core_secret"] = secret
        self._audit(
            "cloud.core.registered" if secret else "cloud.core.reconnected",
            actor_type="user",
            actor_id=user_id,
            subject_type="core",
            subject_id=core["core_id"],
            metadata={"core_version": core.get("core_version")},
        )
        return public

    def permissions(self, entitlements):
        if self.access_policy is not None:
            return self.access_policy.permissions(entitlements)
        # Compatibility fallback for older construction paths. Keep this
        # product-aware so a non-Core entitlement cannot unlock Core.
        if not any(e.get("product") == "core" for e in (entitlements or [])):
            return []
        return [
            "core.view",
            "core.execute",
            "engine.execute",
            "pipeline.run",
            "plugin.run",
            "node.access",
            "runtime.distribution.resolve",
            "runtime.distribution.download",
        ]

    def heartbeat_seat(
        self,
        *,
        user_id,
        core_id,
        core_secret,
        activation_id=None,
        lease_generation=None,
    ):
        """Lightweight online seat authority check; does not issue/sign a grant."""
        now = int(time.time())
        user = self.users.get(user_id)
        core = self.cores.get(core_id)
        if not user or not user.get("email_verified_at") or user.get("status") != "active":
            raise CloudFoundationError("ACCOUNT_NOT_ACTIVE", "Verified active account required.", 403)
        if not core:
            raise CloudFoundationError("CORE_REGISTRATION_NOT_FOUND", "Core registration not found.", 403)
        if str(core.get("user_id") or "") != str(user_id):
            raise CloudFoundationError("CORE_ACCOUNT_MISMATCH", "Core belongs to another account.", 403)
        core_status = str(core.get("status") or "active").lower()
        if core_status == "replaced":
            raise CloudFoundationError("CORE_REPLACED", "This Core was replaced by another activation.", 403)
        if core_status == "deactivated":
            raise CloudFoundationError("CORE_DEACTIVATED", "This Core was deactivated.", 403)
        if core_status != "active":
            raise CloudFoundationError("CORE_REGISTRATION_NOT_FOUND", "Core registration is not active.", 403)
        if not self.cores.verify_secret_record(core, core_secret):
            raise CloudFoundationError("CORE_CREDENTIAL_INVALID", "Core credential invalid.", 403)

        activation = self._activation_for_core_record(core)
        if activation is None:
            raise CloudFoundationError("SEAT_REVOKED", "This Core no longer owns its registered active seat.", 403)
        if activation_id and str(activation.get("activation_id") or "") != str(activation_id):
            raise CloudFoundationError("SEAT_REVOKED", "Activation binding changed.", 403)

        active_entitlements = self.entitlements.active_for_user(user_id, now)
        active_ids = {
            str(e.get("entitlement_id") or "")
            for e in active_entitlements
        }
        if str(activation.get("entitlement_id") or "") not in active_ids:
            raise CloudFoundationError("ACTIVATION_ENTITLEMENT_INACTIVE", "Activation entitlement inactive.", 403)

        # Reuse the same entitlement snapshot for plan authority.
        effective_policy = self.access_policy.resolve_effective_plan_policy(
            active_entitlements
        )
        if not effective_policy or effective_policy.get("enabled", True) is not True:
            raise CloudFoundationError(
                "PLAN_POLICY_DISABLED",
                "The effective Cloud plan is currently disabled.",
                403,
            )

        try:
            checked = self.activations.validate_heartbeat_record(
                activation,
                user_id=user_id,
                core_id=core_id,
                expected_generation=lease_generation,
            )
        except PermissionError as exc:
            code = str(exc) or "SEAT_REVOKED"
            raise CloudFoundationError(code, "This Core no longer owns the seat.", 403)

        telemetry_interval = max(
            300,
            int(os.getenv("CLOUD_SEAT_TELEMETRY_WRITE_SECONDS", "900")),
        )
        wrote_telemetry = False
        if self.activations.telemetry_due(
            checked,
            now=now,
            write_interval_seconds=telemetry_interval,
        ):
            try:
                checked = self.activations.heartbeat(
                    activation_id=checked["activation_id"],
                    user_id=user_id,
                    core_id=core_id,
                    lease_seconds=int(os.getenv("CLOUD_SEAT_LEASE_SECONDS", "1200")),
                    expected_generation=lease_generation,
                    now=now,
                )
                wrote_telemetry = True
            except PermissionError as exc:
                code = str(exc) or "SEAT_REVOKED"
                raise CloudFoundationError(code, "This Core no longer owns the seat.", 403)

        entitlement_id = str(checked.get("entitlement_id") or "")
        entitlement = next(
            (
                e for e in active_entitlements
                if str(e.get("entitlement_id") or "") == entitlement_id
            ),
            {},
        )
        seat_limit = max(1, int(entitlement.get("seat_limit") or 1))
        try:
            seat_active_count = int(
                self.activations.active_count_for_entitlement(entitlement_id)
            )
        except Exception:
            seat_active_count = 1

        return {
            "schema": "core_seat_lease_v1",
            "state": "active",
            "activation_id": checked.get("activation_id"),
            "lease_generation": int(checked.get("lease_generation") or 1),
            "lease_expires_at": int(checked.get("lease_expires_at") or 0),
            "telemetry_persisted": wrote_telemetry,
            "seat_active_count": max(0, min(seat_active_count, seat_limit)),
            "seat_limit": seat_limit,
            "server_time": now,
        }

    def issue_grant(self, user_id, core_id, core_secret):
        now = int(time.time())
        u = self.users.get(user_id)
        core = self.cores.get(core_id)
        if not u or not u.get("email_verified_at") or u.get("status") != "active":
            raise CloudFoundationError("ACCOUNT_NOT_ACTIVE", "Verified active account required.", 403)
        if not core:
            raise CloudFoundationError("CORE_REGISTRATION_NOT_FOUND", "Core registration not found.", 403)
        if str(core.get("user_id") or "") != str(user_id):
            raise CloudFoundationError("CORE_ACCOUNT_MISMATCH", "Core belongs to another account.", 403)
        core_status = str(core.get("status") or "active").lower()
        if core_status == "replaced":
            raise CloudFoundationError("CORE_REPLACED", "This Core was replaced by another activation.", 403)
        if core_status == "deactivated":
            raise CloudFoundationError("CORE_DEACTIVATED", "This Core was deactivated.", 403)
        if core_status != "active":
            raise CloudFoundationError("CORE_REGISTRATION_NOT_FOUND", "Core registration is not active.", 403)
        if not self.cores.verify_secret(core_id, core_secret):
            self._audit(
                "cloud.access_grant.rejected",
                actor_type="core",
                actor_id=core_id,
                subject_type="user",
                subject_id=user_id,
                outcome="denied",
                metadata={"reason": "core_credential_invalid"},
            )
            raise CloudFoundationError("CORE_CREDENTIAL_INVALID", "Core credential invalid.", 403)
        ents = self.entitlements.active_for_user(user_id, now)
        if not ents:
            raise CloudFoundationError("ENTITLEMENT_INACTIVE", "Active entitlement required.", 403)

        entitlement = self._select_core_entitlement(user_id, now)
        activation = self._activation_for_core_record(core)
        if activation is None:
            # Migration-safe backfill only when the registration has no canonical
            # activation_id. If it has one and that seat is inactive, authority
            # has revoked the seat and a fresh verified activation is required.
            if str(core.get("activation_id") or ""):
                raise CloudFoundationError(
                    "SEAT_REVOKED",
                    "This Core no longer owns its registered active seat.",
                    403,
                )
            candidate = self._reserve_activation(
                user_id, entitlement, core.get("machine_hash"), core_id
            )
            activation = self._activate_binding(
                candidate,
                user_id=user_id,
                entitlement=entitlement,
                core_id=core_id,
                machine_hash=core.get("machine_hash"),
            )
            self._audit(
                "cloud.activation.backfilled",
                actor_type="core",
                actor_id=core_id,
                subject_type="activation",
                subject_id=activation.get("activation_id"),
                metadata={"entitlement_id": entitlement.get("entitlement_id")},
            )
        else:
            if str(activation.get("user_id") or "") != str(user_id):
                raise CloudFoundationError(
                    "ACTIVATION_OWNERSHIP_CONFLICT",
                    "Core activation belongs to another account.",
                    403,
                )
            active_ids = {str(e.get("entitlement_id") or "") for e in ents}
            if str(activation.get("entitlement_id") or "") not in active_ids:
                raise CloudFoundationError(
                    "ACTIVATION_ENTITLEMENT_INACTIVE",
                    "Core activation entitlement is inactive.",
                    403,
                )
            self.activations.touch(activation["activation_id"], now)

        # Entitlement convergence invariant: the activation seat used by this Core
        # must be owned by the same effective entitlement that will be projected
        # into the signed grant. This is especially important after Trial -> paid
        # upgrades and for multi-seat BASIC/PRO/MASTER accounts.
        if str(activation.get("entitlement_id") or "") != str(entitlement.get("entitlement_id") or ""):
            previous_activation = activation
            candidate = self._reserve_activation(
                user_id, entitlement, core.get("machine_hash"), core_id
            )
            activation = self._activate_binding(
                candidate,
                user_id=user_id,
                entitlement=entitlement,
                core_id=core_id,
                machine_hash=core.get("machine_hash"),
            )
            if str(previous_activation.get("activation_id") or "") != str(activation.get("activation_id") or ""):
                self.activations.deactivate(
                    previous_activation["activation_id"],
                    reason="effective_entitlement_superseded",
                    now=now,
                )
            # Keep registration metadata aligned with the canonical activation.
            self.cores.register(
                user_id,
                core_id,
                core.get("core_version"),
                core.get("machine_hash"),
                activation_id=activation.get("activation_id"),
                entitlement_id=entitlement.get("entitlement_id"),
            )

        nearest = min(
            [
                int(e["expires_at"])
                for e in ents
                if e.get("expires_at") is not None
                and canonical_plan(e.get("plan")) != "trial"
            ]
            or [now + self.grant_ttl]
        )
        selected_plan = canonical_plan(entitlement.get("plan"))
        grant_ttl = self.grant_ttl
        if selected_plan == "trial":
            # P34F: Trial is no-expiry by account policy, but its OFFLINE grant
            # is deliberately short. Online Agent heartbeat keeps the seat live
            # and refreshes this signed grant before it expires.
            grant_ttl = min(
                grant_ttl,
                max(900, int(os.getenv("CLOUD_TRIAL_OFFLINE_GRANT_TTL_SECONDS", "1800"))),
            )
        expires = min(now + grant_ttl, nearest)
        if expires <= now:
            raise CloudFoundationError("ENTITLEMENT_INACTIVE", "Active entitlement required.", 403)
        permissions = self.permissions(ents)
        if not permissions:
            raise CloudFoundationError("ENTITLEMENT_INACTIVE", "Active Core entitlement required.", 403)
        access = (
            self.access_policy.access_projection(ents, grant_expires_at=expires)
            if self.access_policy is not None
            else {
                "state": "active",
                "product": "core",
                "plan": next((e.get("plan") for e in ents if e.get("product") == "core"), None),
                "source": next((e.get("source_type") for e in ents if e.get("product") == "core"), None),
                "entitlement_id": next((e.get("entitlement_id") for e in ents if e.get("product") == "core"), None),
                "entitlement_expires_at": next((e.get("expires_at") for e in ents if e.get("product") == "core"), None),
                "grant_expires_at": expires,
            }
        )
        # Signed seat projection. Core/UI must not infer seat usage locally.
        seat_limit = max(1, int(entitlement.get("seat_limit") or 1))
        try:
            seat_active_count = int(
                self.activations.active_count_for_entitlement(
                    entitlement["entitlement_id"]
                )
            )
        except Exception:
            seat_active_count = 1
        access["seat_limit"] = seat_limit
        access["seat_active_count"] = max(1, min(seat_active_count, seat_limit))
        access["seat_index"] = activation.get("seat_index")

        offline = (
            self.access_policy.offline_projection(grant_ttl_seconds=expires - now)
            if self.access_policy is not None
            else {"allowed": True, "max_seconds": max(0, expires - now), "requires_valid_grant": True}
        )
        usage_policy = (
            self.access_policy.usage_policy_projection(ents)
            if self.access_policy is not None and hasattr(self.access_policy, "usage_policy_projection")
            else None
        )
        payload = {
            "schema": "core_access_grant_v1",
            "grant_id": str(uuid.uuid4()),
            "user_id": user_id,
            "core_id": core_id,
            "activation": {
                "activation_id": activation.get("activation_id"),
                "entitlement_id": activation.get("entitlement_id"),
                "seat_index": activation.get("seat_index"),
                "lease_generation": max(1, int(activation.get("lease_generation") or 1)),
                "machine_binding": "machine_core",
            },
            "entitlements": [
                {
                    "entitlement_id": e["entitlement_id"],
                    "product": e["product"],
                    "plan": e["plan"],
                    "source": e["source_type"],
                    "expires_at": (
                        None if canonical_plan(e.get("plan")) == "trial" else e.get("expires_at")
                    ),
                }
                for e in ents
            ],
            "access": access,
            "permissions": permissions,
            "offline": offline,
            "issued_at": now,
            "expires_at": expires,
            "issuer": os.getenv("CLOUD_GRANT_ISSUER", "core-factory-cloud"),
            "key_id": os.getenv("CLOUD_SIGNING_KEY_ID", "v1"),
        }
        if usage_policy is not None:
            payload["usage_policy"] = dict(usage_policy)
            # Compatibility only: older Core builds understand Trial through
            # trial_policy. Paid plans are never projected through this legacy field.
            if canonical_plan(access.get("plan")) == "trial":
                payload["trial_policy"] = dict(usage_policy)

        result = {
            "payload": payload,
            "signature": self.signer.sign(payload),
            "key_id": payload["key_id"],
        }
        self._audit(
            "cloud.access_grant.issued",
            actor_type="core",
            actor_id=core_id,
            subject_type="user",
            subject_id=user_id,
            metadata={"grant_id": payload["grant_id"], "expires_at": expires},
        )
        return result

    def activate_licensed_account_by_email(
        self,
        *,
        email,
        machine_hash,
        core_version=None,
        current_user_id=None,
        current_core_id=None,
        current_core_secret=None,
    ):
        """Silently reconcile an EXISTING verified account only with secret Core proof.

        Security policy:
        - email knowledge and machine_hash are NOT account-ownership proof;
        - silent activation requires a persisted Core credential already owned by
          the same Cloud user represented by ``email``;
        - switching to another email/account requires onboarding confirmation by email;
        - stale/missing Core credential also requires confirmation rather than
          same-device credential rotation.
        """
        now = int(time.time())
        email = str(email or "").strip().lower()
        machine_hash = str(machine_hash or "").strip()
        if not email:
            raise CloudFoundationError("EMAIL_REQUIRED", "Email is required.", 400)
        if not machine_hash:
            raise CloudFoundationError("MACHINE_BINDING_REQUIRED", "Machine binding is required.", 400)

        user = self.users.get_by_email(email)
        if not user:
            raise CloudFoundationError(
                "LICENSE_ACCOUNT_NOT_FOUND",
                "No existing licensed account was found for this email.",
                404,
            )
        if not user.get("email_verified_at"):
            raise CloudFoundationError(
                "LICENSE_ACCOUNT_NOT_VERIFIED",
                "This account is not verified. Use Trial/account verification first.",
                409,
            )
        if str(user.get("status") or "") != "active":
            raise CloudFoundationError("ACCOUNT_NOT_ACTIVE", "The account is not active.", 403)

        # A public/stable machine fingerprint is never sufficient to prove that
        # the person operating this installation owns the requested Cloud account.
        # Silent reconnect is allowed only when this Core still possesses the
        # secret credential previously issued to the SAME user/account.
        current_user_id = str(current_user_id or "").strip()
        current_core_id = str(current_core_id or "").strip()
        current_core_secret = str(current_core_secret or "").strip()
        if not all((current_user_id, current_core_id, current_core_secret)):
            raise CloudFoundationError(
                "ACTIVATION_PROOF_REQUIRED",
                "Email confirmation is required to activate this account on this Core.",
                409,
            )
        if current_user_id != str(user["user_id"]):
            raise CloudFoundationError(
                "ACCOUNT_SWITCH_CONFIRMATION_REQUIRED",
                "Email confirmation is required before switching this Core to another account.",
                409,
            )

        proof_core = self.cores.get(current_core_id)
        if (
            not proof_core
            or str(proof_core.get("user_id") or "") != str(user["user_id"])
            or str(proof_core.get("machine_hash") or "") != machine_hash
        ):
            raise CloudFoundationError(
                "CORE_REGISTRATION_INVALID",
                "The saved Core registration cannot prove account ownership. Email confirmation is required.",
                409,
            )
        if not self.cores.verify_secret(current_core_id, current_core_secret):
            raise CloudFoundationError(
                "CORE_CREDENTIAL_INVALID",
                "The saved Core credential is no longer valid. Email confirmation is required.",
                409,
            )

        entitlement = self._select_core_entitlement(user["user_id"], now, machine_hash=machine_hash)
        candidate_core_id = str(uuid.uuid4())
        activation = self._reserve_activation(
            user["user_id"], entitlement, machine_hash, candidate_core_id
        )
        resolved_core_id = str(activation.get("core_id") or candidate_core_id)

        try:
            core, core_secret = self.cores.register(
                user["user_id"],
                resolved_core_id,
                core_version,
                machine_hash,
                activation_id=activation["activation_id"],
                entitlement_id=entitlement["entitlement_id"],
            )
        except PermissionError as exc:
            raise CloudFoundationError(
                "CORE_OWNERSHIP_CONFLICT",
                "Core identity belongs to another account.",
                403,
            ) from exc

        if not core_secret:
            # The caller already proved possession of a valid secret above.
            # Never rotate a Core credential from machine_hash alone.
            if str(core.get("core_id") or "") != current_core_id:
                raise CloudFoundationError(
                    "ACTIVATION_PROOF_REQUIRED",
                    "Email confirmation is required before binding another Core identity.",
                    409,
                )
            grant = self.issue_grant(
                user["user_id"],
                current_core_id,
                current_core_secret,
            )
            public_core = {k: v for k, v in core.items() if k != "core_secret_hash"}
            # Return the already-proven credential so the client contract remains
            # stable without issuing/rotating a new secret.
            public_core["core_secret"] = current_core_secret
            return {
                "schema": "core_email_license_activation_v2",
                "activated": True,
                "reconnected": True,
                "core": public_core,
                "access_grant": grant,
                "entitlement": entitlement,
            }

        activation = self._activate_binding(
            activation,
            user_id=user["user_id"],
            entitlement=entitlement,
            core_id=core["core_id"],
            machine_hash=machine_hash,
        )
        grant = self.issue_grant(user["user_id"], core["core_id"], core_secret)
        public_core = {k: v for k, v in core.items() if k != "core_secret_hash"}
        public_core["core_secret"] = core_secret

        self._audit(
            "cloud.license.email_account_activated",
            actor_type="user",
            actor_id=user["user_id"],
            subject_type="core",
            subject_id=core["core_id"],
            metadata={
                "email": email,
                "entitlement_id": entitlement["entitlement_id"],
                "source_type": entitlement.get("source_type"),
                "plan": entitlement.get("plan"),
                "seat_limit": int(entitlement.get("seat_limit") or 1),
                "activation_id": activation["activation_id"],
            },
        )
        return {
            "schema": "core_email_license_activation_v2",
            "activated": True,
            "reconnected": False,
            "core": public_core,
            "access_grant": grant,
            "entitlement": entitlement,
        }

    def activate_linked_license_account(
        self,
        *,
        email,
        license_key,
        machine_hash,
        core_id=None,
        core_version=None,
    ):
        """Activate a verified account using possession of its already-linked legacy key.

        This is the no-email bridge for migration:
        linked key proof -> account entitlement -> activation seat -> Core credential/grant.
        """
        now = int(time.time())
        email = str(email or "").strip().lower()
        license_key = str(license_key or "").strip()
        machine_hash = str(machine_hash or "").strip()

        if not email:
            raise CloudFoundationError("EMAIL_REQUIRED", "Email is required.", 400)
        if not license_key:
            raise CloudFoundationError("LICENSE_KEY_REQUIRED", "License key is required.", 400)
        if not machine_hash:
            raise CloudFoundationError("MACHINE_BINDING_REQUIRED", "Machine binding is required.", 400)

        user = self.users.get_by_email(email)
        if not user:
            raise CloudFoundationError("ACCOUNT_NOT_FOUND", "No Cloud account exists for this email.", 404)
        if not user.get("email_verified_at"):
            raise CloudFoundationError("EMAIL_NOT_VERIFIED", "The account email is not verified.", 403)
        if str(user.get("status") or "") != "active":
            raise CloudFoundationError("ACCOUNT_NOT_ACTIVE", "The Cloud account is not active.", 403)

        legacy = self.legacy_licenses.get_by_key(license_key)
        if not legacy:
            raise CloudFoundationError("LICENSE_NOT_FOUND", "License key not found.", 404)

        if bool((legacy.get("security") or {}).get("revoked", False)) or str(legacy.get("status") or "").lower() == "revoked":
            raise CloudFoundationError("LICENSE_REVOKED", "License key is revoked.", 403)

        expires_at = legacy.get("expire_at")
        if expires_at is not None and int(expires_at) <= now:
            raise CloudFoundationError("LICENSE_EXPIRED", "License key is expired.", 403)

        link = dict(legacy.get("account_link") or {})
        if str(link.get("status") or "") != "linked":
            raise CloudFoundationError(
                "LICENSE_NOT_LINKED_TO_ACCOUNT",
                "This License Key has not been linked to a Cloud account.",
                409,
            )
        if str(link.get("user_id") or "") != str(user["user_id"]):
            raise CloudFoundationError(
                "LICENSE_ACCOUNT_MISMATCH",
                "This License Key is linked to a different Cloud account.",
                403,
            )
        linked_email = str(link.get("email") or "").strip().lower()
        if linked_email and linked_email != email:
            raise CloudFoundationError(
                "LICENSE_EMAIL_MISMATCH",
                "This License Key is linked to a different email address.",
                403,
            )

        entitlement_id = str(link.get("entitlement_id") or "")
        entitlement = self.entitlements.get(entitlement_id) if entitlement_id else None
        if not entitlement:
            raise CloudFoundationError(
                "ENTITLEMENT_NOT_FOUND",
                "The linked account entitlement is missing.",
                409,
            )
        if str(entitlement.get("subject_id") or "") != str(user["user_id"]):
            raise CloudFoundationError("ENTITLEMENT_OWNERSHIP_CONFLICT", "Entitlement ownership mismatch.", 403)
        if str(entitlement.get("status") or "") != "active":
            raise CloudFoundationError("ENTITLEMENT_INACTIVE", "Linked entitlement is not active.", 403)
        ent_exp = entitlement.get("expires_at")
        if ent_exp is not None and int(ent_exp) <= now:
            raise CloudFoundationError("ENTITLEMENT_EXPIRED", "Linked entitlement is expired.", 403)

        candidate_core_id = str(core_id or uuid.uuid4())
        activation = self._reserve_activation(
            user["user_id"], entitlement, machine_hash, candidate_core_id
        )
        resolved_core_id = str(activation.get("core_id") or candidate_core_id)

        try:
            core, core_secret = self.cores.register(
                user["user_id"],
                resolved_core_id,
                core_version,
                machine_hash,
                activation_id=activation["activation_id"],
                entitlement_id=entitlement["entitlement_id"],
            )
        except PermissionError as exc:
            raise CloudFoundationError(
                "CORE_OWNERSHIP_CONFLICT",
                "Core ID belongs to another account.",
                403,
            ) from exc

        if not core_secret:
            # Same device/Core already exists: rotate rather than replay old secret.
            public_core, grant = self._recover_same_device_core(
                user_id=user["user_id"],
                entitlement=entitlement,
                core=core,
                machine_hash=machine_hash,
            )
            return {
                "schema": "core_linked_license_activation_v1",
                "activated": True,
                "reconnected": True,
                "credential_rotated": True,
                "core": public_core,
                "access_grant": grant,
                "entitlement": entitlement,
            }

        activation = self._activate_binding(
            activation,
            user_id=user["user_id"],
            entitlement=entitlement,
            core_id=core["core_id"],
            machine_hash=machine_hash,
        )
        grant = self.issue_grant(user["user_id"], core["core_id"], core_secret)
        public_core = {k: v for k, v in core.items() if k != "core_secret_hash"}
        public_core["core_secret"] = core_secret

        self._audit(
            "cloud.license.linked_key_account_activated",
            actor_type="user",
            actor_id=user["user_id"],
            subject_type="core",
            subject_id=core["core_id"],
            metadata={
                "license_key": license_key,
                "entitlement_id": entitlement["entitlement_id"],
                "activation_id": activation["activation_id"],
            },
        )

        return {
            "schema": "core_linked_license_activation_v1",
            "activated": True,
            "reconnected": False,
            "core": public_core,
            "access_grant": grant,
            "entitlement": entitlement,
        }

    def admin_link_legacy_license_to_account(self, *, email, license_key):
        """One-time bridge from legacy key authority into account entitlement."""
        now = int(time.time())
        email = str(email or "").strip().lower()
        license_key = str(license_key or "").strip()
        if not email:
            raise CloudFoundationError("EMAIL_REQUIRED", "Email is required.", 400)
        if not license_key:
            raise CloudFoundationError("LICENSE_KEY_REQUIRED", "License key is required.", 400)

        user = self.users.get_by_email(email)
        if not user:
            raise CloudFoundationError(
                "ACCOUNT_NOT_FOUND", "No Cloud account exists for this email.", 404
            )
        if not user.get("email_verified_at"):
            raise CloudFoundationError(
                "EMAIL_NOT_VERIFIED",
                "The account email must be verified before linking a license key.",
                409,
            )
        if str(user.get("status") or "") != "active":
            raise CloudFoundationError(
                "ACCOUNT_NOT_ACTIVE", "The Cloud account is not active.", 409
            )

        legacy = self.legacy_licenses.get_by_key(license_key)
        if not legacy:
            raise CloudFoundationError("LICENSE_NOT_FOUND", "Legacy license key not found.", 404)

        if bool((legacy.get("security") or {}).get("revoked", False)) or str(legacy.get("status") or "").lower() == "revoked":
            raise CloudFoundationError("LICENSE_REVOKED", "Legacy license is revoked.", 409)

        expires_at = legacy.get("expire_at")
        if expires_at is not None and int(expires_at) <= now:
            raise CloudFoundationError("LICENSE_EXPIRED", "Legacy license is expired.", 409)

        link = dict(legacy.get("account_link") or {})
        linked_user = str(link.get("user_id") or "")
        if linked_user and linked_user != str(user["user_id"]):
            raise CloudFoundationError(
                "LICENSE_ALREADY_LINKED_TO_ANOTHER_ACCOUNT",
                "This license key is already linked to another Cloud account.",
                409,
            )

        machines = []
        for value in legacy.get("machine_hashes") or []:
            value = str(value or "").strip()
            if value and value not in machines:
                machines.append(value)

        seat_limit = max(
            1,
            int(legacy.get("device_limit") or 1),
            len(machines),
        )
        plan = str(legacy.get("plan") or "legacy").strip().lower()
        created_at = int(
            ((legacy.get("time") or {}).get("created_at"))
            or legacy.get("created_at")
            or now
        )

        entitlement = self.entitlements.issue_once(
            user["user_id"],
            "core",
            plan,
            "legacy_license",
            license_key,
            created_at,
            None if expires_at is None else int(expires_at),
            seat_limit=seat_limit,
            activation_policy={
                "binding": "machine_core",
                "transfer": "manual",
                "legacy_key": license_key,
            },
        )

        try:
            imported = self.activations.import_legacy_machine_bindings(
                entitlement=entitlement,
                user_id=user["user_id"],
                machine_hashes=machines,
            )
        except RuntimeError as exc:
            raise CloudFoundationError(
                str(exc),
                "Legacy device bindings could not be imported into account seats.",
                409,
            ) from exc

        try:
            legacy = self.legacy_licenses.claim_account_link(
                license_key,
                user_id=user["user_id"],
                email=user.get("email") or email,
                entitlement_id=entitlement["entitlement_id"],
            )
        except KeyError as exc:
            raise CloudFoundationError("LICENSE_NOT_FOUND", "Legacy license key not found.", 404) from exc
        except PermissionError as exc:
            raise CloudFoundationError(
                "LICENSE_ALREADY_LINKED_TO_ANOTHER_ACCOUNT",
                "This license key is already linked to another Cloud account.",
                409,
            ) from exc

        self._audit(
            "cloud.license.legacy_linked",
            actor_type="owner",
            actor_id="owner",
            subject_type="user",
            subject_id=user["user_id"],
            metadata={
                "email": user.get("email"),
                "license_key": license_key,
                "entitlement_id": entitlement["entitlement_id"],
                "seat_limit": seat_limit,
                "legacy_bound_machines": len(machines),
            },
        )

        return {
            "account": {
                "user_id": user["user_id"],
                "email": user.get("email"),
                "email_verified": True,
                "status": user.get("status"),
            },
            "legacy_license": {
                "license_key": license_key,
                "plan": legacy.get("plan"),
                "expire_at": legacy.get("expire_at"),
                "device_limit": legacy.get("device_limit"),
                "bound_devices": len(machines),
                "account_link": legacy.get("account_link"),
            },
            "entitlement": entitlement,
            "imported_seats": imported,
            "migration_policy": {
                "existing_local_devices_remain_valid": True,
                "new_local_binding_allowed": False,
                "new_devices_use_account_activation": True,
            },
        }

    def deactivate_current_core(self, *, user_id, core_id, core_secret):
        """Deactivate exactly the calling Core and release its entitlement seat.

        Proof is possession of the current Core secret. This never deactivates
        another Core and therefore remains safe for multi-seat Personal Core use.
        """
        user_id = str(user_id or "").strip()
        core_id = str(core_id or "").strip()
        core_secret = str(core_secret or "").strip()
        if not all((user_id, core_id, core_secret)):
            raise CloudFoundationError(
                "CORE_DEACTIVATION_PROOF_REQUIRED",
                "Current Core identity and credential are required.",
                400,
            )

        core = self.cores.get(core_id)
        if not core:
            raise CloudFoundationError("CORE_REGISTRATION_NOT_FOUND", "Core registration not found.", 403)
        if str(core.get("user_id") or "") != user_id:
            raise CloudFoundationError("CORE_ACCOUNT_MISMATCH", "Core belongs to another account.", 403)
        core_status = str(core.get("status") or "active").lower()
        if core_status == "replaced":
            raise CloudFoundationError("CORE_REPLACED", "This Core was replaced by another activation.", 403)
        if core_status == "deactivated":
            raise CloudFoundationError("CORE_DEACTIVATED", "This Core was already deactivated.", 403)
        if core_status != "active":
            raise CloudFoundationError("CORE_REGISTRATION_NOT_FOUND", "Core registration is not active.", 403)
        if not self.cores.verify_secret(core_id, core_secret):
            raise CloudFoundationError(
                "CORE_CREDENTIAL_INVALID",
                "Core credential invalid.",
                403,
            )

        activation = self._activation_for_core_record(core)
        if not activation:
            raise CloudFoundationError(
                "CORE_ACTIVATION_NOT_FOUND",
                "This Core does not own its registered active seat.",
                409,
            )
        if str(activation.get("user_id") or "") != user_id:
            raise CloudFoundationError(
                "ACTIVATION_OWNERSHIP_CONFLICT",
                "Core activation belongs to another account.",
                403,
            )

        entitlement_id = str(activation.get("entitlement_id") or "")
        result = self.activations.deactivate(
            activation["activation_id"],
            reason="user_deactivate_current_core",
        )
        try:
            self.cores.mark_deactivated(
                core_id,
                reason="user_deactivate_current_core",
            )
        except Exception:
            # Seat authority is the activation record. Registration status is
            # lifecycle/audit metadata and must not block seat release.
            pass

        entitlement = self.entitlements.get(entitlement_id) if entitlement_id else None
        seat_limit = max(1, int((entitlement or {}).get("seat_limit") or 1))
        try:
            active_count = int(self.activations.active_count_for_entitlement(entitlement_id))
        except Exception:
            active_count = 0

        self._audit(
            "cloud.activation.deactivated",
            actor_type="core",
            actor_id=core_id,
            subject_type="activation",
            subject_id=activation.get("activation_id"),
            metadata={
                "entitlement_id": entitlement_id,
                "reason": "user_deactivate_current_core",
                "seat_active_count": active_count,
                "seat_limit": seat_limit,
            },
        )
        return {
            "schema": "core_self_deactivation_v1",
            "deactivated": True,
            "core_id": core_id,
            "activation_id": activation.get("activation_id"),
            "entitlement_id": entitlement_id or None,
            "seat_active_count": max(0, active_count),
            "seat_limit": seat_limit,
        }

    def admin_list_entitlement_seats(self, *, entitlement_id):
        entitlement = self.entitlements.get(entitlement_id)
        if not entitlement:
            raise CloudFoundationError(
                "ENTITLEMENT_NOT_FOUND", "Entitlement not found.", 404
            )
        seats = self.activations.list_for_entitlement(entitlement_id)
        return {
            "entitlement": entitlement,
            "seats": seats,
            "active_seats": sum(1 for x in seats if x.get("status") == "active"),
        }

    def admin_deactivate_seat(
        self,
        *,
        entitlement_id,
        activation_id,
        reason="admin_deactivate",
    ):
        entitlement = self.entitlements.get(entitlement_id)
        if not entitlement:
            raise CloudFoundationError(
                "ENTITLEMENT_NOT_FOUND", "Entitlement not found.", 404
            )
        activation = self.activations.get(activation_id)
        if not activation:
            raise CloudFoundationError(
                "ACTIVATION_NOT_FOUND", "Activation seat not found.", 404
            )
        if str(activation.get("entitlement_id") or "") != str(entitlement_id):
            raise CloudFoundationError(
                "ACTIVATION_ENTITLEMENT_MISMATCH",
                "Activation does not belong to this entitlement.",
                409,
            )

        plan = str(entitlement.get("plan") or "").lower()
        source_type = str(entitlement.get("source_type") or "").lower()
        is_trial = plan == "trial" or source_type == "trial"

        # Trial seats are admin-reset only by design. This API is owner/admin only,
        # so it is allowed, but audit metadata explicitly records the reset.
        result = self.activations.deactivate(
            activation_id,
            reason="trial_admin_reset" if is_trial else str(reason or "admin_deactivate"),
        )

        self._audit(
            "cloud.activation.deactivated",
            actor_type="owner",
            actor_id="owner",
            subject_type="activation",
            subject_id=activation_id,
            metadata={
                "entitlement_id": entitlement_id,
                "plan": plan,
                "source_type": source_type,
                "trial_reset": is_trial,
                "reason": result.get("deactivation_reason"),
            },
        )
        return {
            "entitlement": entitlement,
            "activation": result,
            "trial_reset": is_trial,
        }

    def admin_account_seat_overview(self, *, email):
        user = self.users.get_by_email(str(email or ""))
        if not user:
            raise CloudFoundationError(
                "ACCOUNT_NOT_FOUND", "No Cloud account exists for this email.", 404
            )
        entitlements = self.entitlements.active_for_user(user["user_id"])
        result = []
        for entitlement in entitlements:
            if entitlement.get("product") != "core":
                continue
            seats = self.activations.list_for_entitlement(
                entitlement["entitlement_id"]
            )
            result.append({
                "entitlement": entitlement,
                "active_seats": sum(
                    1 for x in seats if x.get("status") == "active"
                ),
                "seat_limit": int(entitlement.get("seat_limit") or 1),
                "seats": seats,
            })
        return {
            "account": {
                "user_id": user["user_id"],
                "email": user.get("email"),
                "email_verified": bool(user.get("email_verified_at")),
                "status": user.get("status"),
            },
            "core_entitlements": result,
        }

    def admin_issue_manual_entitlement(
        self,
        *,
        email,
        product="core",
        plan="basic",
        seat_limit=1,
        starts_at=None,
        expires_at=None,
        duration_days=None,
        source_id=None,
    ):
        """Issue/update a manual entitlement to an existing verified account."""
        now = int(time.time())
        user = self.users.get_by_email(str(email or ""))
        if not user:
            raise CloudFoundationError(
                "ACCOUNT_NOT_FOUND",
                "No Cloud account exists for this email.",
                404,
            )
        if not user.get("email_verified_at"):
            raise CloudFoundationError(
                "EMAIL_NOT_VERIFIED",
                "The account email must be verified before a manual license can be issued.",
                409,
            )
        if str(user.get("status") or "") != "active":
            raise CloudFoundationError(
                "ACCOUNT_NOT_ACTIVE",
                "The account is not active.",
                409,
            )

        product = str(product or "core").strip().lower()
        plan = canonical_plan(plan or "basic")
        if not product:
            raise CloudFoundationError("PRODUCT_REQUIRED", "Product is required.", 400)
        if not plan:
            raise CloudFoundationError("PLAN_REQUIRED", "Plan is required.", 400)
        if plan not in {"basic", "pro", "master"}:
            raise CloudFoundationError(
                "PLAN_INVALID",
                "Manual account plan must be BASIC, PRO, or MASTER.",
                400,
            )

        try:
            seat_limit = max(1, int(seat_limit or 1))
        except Exception as exc:
            raise CloudFoundationError(
                "SEAT_LIMIT_INVALID", "Seat limit must be a positive integer.", 400
            ) from exc

        starts_at = now if starts_at is None else int(starts_at)
        if expires_at is not None and duration_days is not None:
            raise CloudFoundationError(
                "ENTITLEMENT_EXPIRY_AMBIGUOUS",
                "Use either expires_at or duration_days, not both.",
                400,
            )
        if duration_days is not None:
            try:
                days = int(duration_days)
            except Exception as exc:
                raise CloudFoundationError(
                    "DURATION_INVALID", "duration_days must be an integer.", 400
                ) from exc
            if days <= 0:
                raise CloudFoundationError(
                    "DURATION_INVALID", "duration_days must be greater than zero.", 400
                )
            expires_at = starts_at + days * 86400
        elif expires_at is not None:
            expires_at = int(expires_at)

        if expires_at is not None and expires_at <= starts_at:
            raise CloudFoundationError(
                "ENTITLEMENT_EXPIRY_INVALID",
                "Entitlement expiry must be after its start time.",
                400,
            )

        source_id = str(source_id or f"owner:{product}").strip()
        entitlement = self.entitlements.upsert_manual(
            subject_id=user["user_id"],
            product=product,
            plan=plan,
            starts_at=starts_at,
            expires_at=expires_at,
            seat_limit=seat_limit,
            source_id=source_id,
            activation_policy={
                "binding": "machine_core" if product == "core" else "account",
                "transfer": "manual",
            },
        )

        # If this is an update, never permit seat_limit below already active seats.
        active_seats = (
            self.activations.active_count_for_entitlement(entitlement["entitlement_id"])
            if product == "core"
            else 0
        )
        if active_seats > seat_limit:
            # Restore the minimum safe value immediately.
            entitlement = self.entitlements.upsert_manual(
                subject_id=user["user_id"],
                product=product,
                plan=plan,
                starts_at=starts_at,
                expires_at=expires_at,
                seat_limit=active_seats,
                source_id=source_id,
                activation_policy={
                    "binding": "machine_core" if product == "core" else "account",
                    "transfer": "manual",
                },
            )
            raise CloudFoundationError(
                "SEAT_LIMIT_BELOW_ACTIVE",
                f"Cannot reduce seat limit below {active_seats} active Core activation seat(s).",
                409,
            )

        self._audit(
            "cloud.entitlement.manual_issued",
            actor_type="owner",
            actor_id="owner",
            subject_type="user",
            subject_id=user["user_id"],
            metadata={
                "email": user.get("email"),
                "entitlement_id": entitlement["entitlement_id"],
                "product": product,
                "plan": plan,
                "seat_limit": seat_limit,
                "expires_at": expires_at,
                "source_id": source_id,
            },
        )
        return {
            "account": {
                "user_id": user["user_id"],
                "email": user.get("email"),
                "email_verified": True,
                "status": user.get("status"),
            },
            "entitlement": entitlement,
            "active_core_seats": active_seats,
        }

    def admin_account_license_status(self, *, email):
        user = self.users.get_by_email(str(email or ""))
        if not user:
            raise CloudFoundationError("ACCOUNT_NOT_FOUND", "No Cloud account exists for this email.", 404)
        entitlements = self.entitlements.active_for_user(user["user_id"])
        core_entitlements = [e for e in entitlements if e.get("product") == "core"]
        core_status = []
        for entitlement in core_entitlements:
            core_status.append({
                "entitlement": entitlement,
                "active_seats": self.activations.active_count_for_entitlement(
                    entitlement["entitlement_id"]
                ),
            })
        return {
            "account": {
                "user_id": user["user_id"],
                "email": user.get("email"),
                "email_verified": bool(user.get("email_verified_at")),
                "status": user.get("status"),
            },
            "active_entitlements": entitlements,
            "core_entitlements": core_status,
        }

    def status(self, user_id):
        u = self.users.get(user_id)
        if not u:
            return {"registered": False}
        trial = self.trials.get(user_id)
        ents = self.entitlements.active_for_user(user_id)
        return {
            "registered": True,
            "user_id": user_id,
            "email": u.get("email"),
            "account_status": u.get("status"),
            "email_verified": bool(u.get("email_verified_at")),
            "email_verified_at": u.get("email_verified_at"),
            "trial": trial,
            "active_entitlements": ents,
        }
