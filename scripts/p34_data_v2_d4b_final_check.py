from pathlib import Path
R=Path(__file__).resolve().parents[1]
a=(R/"server/repositories/activation_repository.py").read_text(encoding="utf-8")
assert "DataV2Bridge" in a
assert 'operations_collection("entitlement_activations")' in a
assert 'operations_doc("entitlement_activations"' in a
assert "def _legacy_ref" in a
t=(R/"server/repositories/trial_repository.py").read_text(encoding="utf-8")
assert "DataV2Bridge" in t and "trial_machine_index" in t and "legacy_fallback" in t
r=(R/"server/services/data_v2_retention_service.py").read_text(encoding="utf-8")
assert "machine_trials intentionally have no automatic delete" in r
assert '"machine_trials"' in r and '"entitlement_activations"' in r
app=(R/"server/app.py").read_text(encoding="utf-8")
assert "/v1/cloud/admin/data-v2/final-status" in app
print("CLOUD DATA V2 D4B FINAL: PASS")
