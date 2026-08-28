from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rank=(ROOT/"server/services/account_rank.py").read_text(encoding="utf-8")
seat=(ROOT/"server/services/seat_upgrade_service.py").read_text(encoding="utf-8")
repo=(ROOT/"server/repositories/seat_upgrade_repository.py").read_text(encoding="utf-8")
wallet=(ROOT/"server/services/wallet_service.py").read_text(encoding="utf-8")
app=(ROOT/"server/app.py").read_text(encoding="utf-8")
foundation=(ROOT/"server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
assert '("MASTER", 5000)' in rank
assert '"SEAT_PLUS_1"' in seat and '"credits": 100' in seat
assert '"SEAT_PLUS_3"' in seat and '"credits": 250' in seat
assert '"SEAT_PLUS_5"' in seat and '"credits": 400' in seat
assert "complete_once" in repo and "purchased_seats" in repo
assert '"lifetime_spent_credits"' in wallet and '"rank"' in wallet
assert "/v1/cloud/seat-upgrades/purchase" in app
assert "_effective_seat_limit" in foundation
print("P34.6 CLOUD SEAT + RANK: PASS")
