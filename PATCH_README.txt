CORE FACTORY CLOUD 3.4.x — Credit Order Pending State Fix

Modified:
- server/repositories/credit_order_repository.py
- scripts/p34_data_v2_credit_order_state_check.py

Fix:
1. In Data V2 mode, admin credit-order listing reads canonical accounts/*/orders documents via collection_group("orders") instead of stale legacy credit_orders.
2. Status filtering is applied to canonical V2 order state.
3. In v2_compat + legacy shadow-write mode, completion/rejection patches also synchronize the legacy shadow document.

Expected invariant:
Approve PENDING order -> canonical status completed -> one idempotent Wallet grant -> admin list(PENDING) no longer contains the order.

No Wallet/Credit/Plugin contract change.
