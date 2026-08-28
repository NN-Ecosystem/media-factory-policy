Render startup hotfix

Cause:
The transient lifecycle patch typed its cleanup endpoint with
CloudAdminOrphanCleanupRequest. That request model exists only when the preceding
Account Lifecycle + Maintenance app.py patch has also been merged. If app.py was
overwritten by the transient patch instead of merged on top, module import fails
with NameError before Uvicorn can start.

Fix:
- Add a self-contained CloudAdminTransientCleanupRequest model.
- Use it only for /v1/cloud/admin/maintenance/transients/cleanup.
- Remove the transient endpoint's dependency on the orphan-cleanup patch model.

Verification:
- server/app.py py_compile: PASS
- request model definition appears before endpoint declaration: PASS

Apply this hotfix over the currently deployed transient lifecycle patch.
