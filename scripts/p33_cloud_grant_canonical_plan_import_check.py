from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]
path = root / "server/services/cloud_foundation_service.py"
src = path.read_text(encoding="utf-8")
tree = ast.parse(src)

imported = False
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom) and node.module == "server.services.cloud_access_policy":
        if any(alias.name == "canonical_plan" for alias in node.names):
            imported = True
            break

assert imported, "canonical_plan must be imported from cloud_access_policy"

start = src.index("def issue_grant")
end = src.index("def activate_licensed_account_by_email", start)
issue = src[start:end]
assert 'canonical_plan(access.get("plan"))' in issue

print("P33 CLOUD GRANT CANONICAL PLAN IMPORT: PASSED")
