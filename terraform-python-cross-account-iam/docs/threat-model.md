# Threat model

| Threat | Control | Residual consideration |
|---|---|---|
| Untrusted account assumes role | Exact trusted source role ARN and required external ID | Correct source identity lifecycle still matters |
| Confused deputy in vendor integration | Per-integration external ID condition | External ID is not authentication by itself |
| Compromised pipeline gains broad access | Source role allowlist and narrow target policy | Pipeline compromise can use currently granted session permissions |
| Credential leakage | STS temporary credentials, no logging/persistence | Caller must protect in-memory credential use |
| Permission expansion | Terraform review, policy checks, boundary/SCP | Static checks cannot resolve every IAM action/resource rule |
| Configuration drift | Terraform plan/refresh and reviewed reconciliation | Live idempotency and deployment are not tested here |

Assumptions: source role is controlled by the organization; external ID is injected through an approved secret channel; environment accounts and resource ARNs are reviewed before use.
