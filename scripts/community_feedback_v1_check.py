from pathlib import Path
root=Path(__file__).resolve().parents[1]
app=(root/'server/app.py').read_text()
svc=(root/'server/services/store_comment_service.py').read_text()
repo=(root/'server/repositories/store_comment_repository.py').read_text()
assert '/v1/public/store/comments' in app
assert '/v1/public/store/items/{item_id}/comments' in app  # temporary backward compatibility
assert '/v1/cloud/store/comments' in app
assert 'verify_secret' in svc
assert 'account_email' in repo and 'show_email' in repo
assert 'row.get("account_email") if row.get("show_email") else None' in svc
assert 'FieldFilter' in repo
assert 'def list_recent' in repo
assert 'def list_public_global' in svc
print('COMMUNITY-FEEDBACK-V1-CLOUD: PASSED')
