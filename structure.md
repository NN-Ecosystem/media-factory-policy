Tổng kiến trúc
ecosystem_verify/
│
├── server/
├── agent/
├── shared/
└── examples/
1. Shared Layer
shared/
│
├── models/
│   ├── user.py
│   ├── machine.py
│   ├── feature.py
│   ├── token.py
│   └── license.py
│
├── enums/
│   ├── feature_tier.py
│   ├── feature_status.py
│   └── verify_status.py
│
└── constants.py
feature.py
@dataclass
class Feature:
    name: str
    tier: str
    capabilities: list[str]
token.py
@dataclass
class LicenseToken:
    uid: str
    machine_id: str
    expire_at: int
    features: dict
2. Server
server/
│
├── api/
│   ├── verify_api.py
│   ├── machine_api.py
│   ├── feature_api.py
│   └── subscription_api.py
│
├── services/
│   ├── verify_service.py
│   ├── license_service.py
│   ├── feature_service.py
│   ├── machine_service.py
│   └── token_service.py
│
├── repositories/
│   ├── user_repo.py
│   ├── machine_repo.py
│   ├── license_repo.py
│   └── feature_repo.py
│
├── security/
│   ├── signer.py
│   ├── key_manager.py
│   └── machine_hash.py
│
├── database/
│   └── models.py
│
└── app.py
verify_service.py
verify()

validate_machine()

validate_license()

build_token()
token_service.py

V1:

create_token()

V2:

sign_token()
3. Agent
agent/
│
├── api/
│   ├── license_api.py
│   ├── feature_api.py
│   └── status_api.py
│
├── managers/
│   ├── license_manager.py
│   ├── feature_manager.py
│   ├── cache_manager.py
│   └── verify_manager.py
│
├── cache/
│   ├── token_cache.py
│   └── cache_storage.py
│
├── security/
│   ├── signature_verifier.py
│   ├── machine_info.py
│   └── machine_hash.py
│
├── models/
│   └── local_token.py
│
└── agent.py
license_manager.py
load_cache()

verify_server()

refresh_token()

is_expired()
feature_manager.py

Đây là phần quan trọng nhất.

has()

tier()

capabilities()

can()

Ví dụ:

feature.has("render")

feature.tier("render")

feature.can("render", "4k")
4. Cache
agent_data/
│
├── license_cache.json
├── machine.json
└── verify_state.json
license_cache.json
{
    "expire": 1751234567,

    "features": {
        "render": {
            "tier": "pro"
        }
    }
}
5. App Integration Layer

Ví dụ Media Factory.

media_factory/
│
├── services/
│   └── license_service.py
from ecosystem_agent import feature

if feature.has("render"):
    render()

Meeting Intelligence:

if feature.has("transcribe"):
    transcribe()

Workspace:

if feature.has("workflow"):
    open_workflow()
6. V2 Security
server/
    private.pem

agent/
    public.pem

Thêm:

agent/security/
    signature_verifier.py

server/security/
    signer.py
7. V3 Capability
feature.can("render", "batch")

feature.can("render", "gpu")

feature.can("ai", "cloud")
Cấu trúc cuối cùng
ecosystem_verify/

    shared/
        models/
        enums/

    server/
        api/
        services/
        repositories/
        security/

    agent/
        api/
        managers/
        cache/
        security/

    examples/
        media_factory/
        workspace_os/
        meeting_ai/