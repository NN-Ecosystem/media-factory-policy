from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
service=(ROOT/"server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
start=service.index("    def heartbeat_seat(")
end=service.index("\n    def _require_active_core_identity",start)
hb=service[start:end]
assert "active_for_user" not in hb
assert "self.entitlements.get(entitlement_id)" in hb
assert "if wrote_telemetry:" in hb
assert '"seat_active_count"' in hb and '"seat_limit"' in hb
print("P34.8 CLOUD HEARTBEAT READ-MINIMAL: PASS")
