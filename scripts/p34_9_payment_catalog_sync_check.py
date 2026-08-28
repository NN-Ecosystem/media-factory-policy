from server.services.credit_order_service import DEFAULT_PACKAGES, canonical_credit_package_id

EXPECTED = [
    ("CORE_CREDIT_200", 200, 500),
    ("CORE_CREDIT_500", 500, 1000),
    ("CORE_CREDIT_1200", 1200, 2000),
    ("CORE_CREDIT_3500", 3500, 5000),
    ("CORE_CREDIT_8000", 8000, 10000),
]
actual=[(x["package_id"],x["credits"],x["price_minor"]) for x in DEFAULT_PACKAGES]
assert actual == EXPECTED, (actual, EXPECTED)
assert canonical_credit_package_id("CREDIT_STARTER_100") == "CORE_CREDIT_200"
assert canonical_credit_package_id("CREDIT_POWER_4000") == "CORE_CREDIT_8000"
print("P34.9 payment/catalog identity sync: PASS")
