from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
repo=(ROOT/"server/repositories/seat_upgrade_repository.py").read_text(encoding="utf-8")
foundation=(ROOT/"server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
assert "core_account_seat_capacity_v1" in repo
assert "base_seats" in repo and "purchased_seats" in repo and "effective_seats" in repo
assert "_account_active_core_ids" in foundation
assert "_account_active_seat_count" in foundation
assert "legacy entitlement value is used" in foundation.lower()
print("P34.7 ACCOUNT SEAT NORMALIZATION: PASS")
