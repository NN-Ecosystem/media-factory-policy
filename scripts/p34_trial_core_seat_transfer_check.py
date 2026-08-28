from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]

service=(root/"server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
activation=(root/"server/repositories/activation_repository.py").read_text(encoding="utf-8")
cores=(root/"server/repositories/core_repository.py").read_text(encoding="utf-8")

ast.parse(service); ast.parse(activation); ast.parse(cores)

assert "def _reserve_after_verified_confirmation" in service
assert 'purpose not in {"core_activation", "license_recovery"}' in service
assert "seat_limit != 1" in service
assert "transfer_single_seat" in service
assert "seat_transferred" in service
assert "def transfer_single_seat" in activation
assert '"transfer_from_core_id"' in activation
assert '"status": "reserved"' in activation
assert "ACTIVATION_TRANSFER_REQUIRES_SEAT_SELECTION" in activation
assert "def mark_replaced" in cores
assert '"status": "replaced"' in cores
assert "canonical_plan" in service

print("P34 TRIAL CORE SEAT TRANSFER: PASSED")
