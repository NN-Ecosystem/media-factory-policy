from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
service=(ROOT/"server/services/cloud_foundation_service.py").read_text(encoding="utf-8")
start=service.index("    def activate_licensed_account_by_email(")
end=service.index("\n    def activate_linked_license_account(", start)
section=service[start:end]
assert 'core_status in {"replaced", "deactivated"}' in section
assert '"ACTIVATION_PROOF_REQUIRED"' in section
assert "complete_onboarding()" in section
print("P34.10 REPLACED CORE REACTIVATION: PASS")
