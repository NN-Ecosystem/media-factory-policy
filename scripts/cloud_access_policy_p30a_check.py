from server.services.cloud_access_policy import CloudAccessPolicy


def main():
    p = CloudAccessPolicy(offline_allowed=True, offline_max_seconds=43200)
    trial = [{
        "entitlement_id": "ent-trial",
        "subject_id": "u1",
        "product": "core",
        "plan": "trial",
        "status": "active",
        "source_type": "trial",
        "starts_at": 100,
        "expires_at": 1000,
    }]
    assert "engine.execute" in p.permissions(trial)
    access = p.access_projection(trial, grant_expires_at=500)
    assert access["state"] == "active"
    assert access["product"] == "core"
    assert access["plan"] == "trial"
    assert access["entitlement_expires_at"] == 1000
    assert access["grant_expires_at"] == 500
    off = p.offline_projection(grant_ttl_seconds=3600)
    assert off == {"allowed": True, "max_seconds": 3600, "requires_valid_grant": True}

    unrelated = [{
        "entitlement_id": "plugin-ent",
        "product": "plugin_x",
        "plan": "pro",
        "status": "active",
        "source_type": "subscription",
        "starts_at": 100,
        "expires_at": 2000,
    }]
    assert p.permissions(unrelated) == []
    assert p.access_projection(unrelated, grant_expires_at=500)["state"] == "inactive"

    multiple = trial + [{
        "entitlement_id": "ent-lifetime",
        "product": "core",
        "plan": "lifetime",
        "status": "active",
        "source_type": "admin_grant",
        "starts_at": 150,
        "expires_at": None,
    }]
    assert p.access_projection(multiple, grant_expires_at=500)["entitlement_id"] == "ent-lifetime"
    print("P30A-CLOUD-ACCESS-POLICY-CHECK PASSED")


if __name__ == "__main__":
    main()
