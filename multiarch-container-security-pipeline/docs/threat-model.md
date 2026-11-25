# Threat model

## Assets

Source integrity, build runner, OCI image and its digest, cloud federation trust, registry contents, scan results, signatures, and release metadata.

## Threats and controls

- **Untrusted pull request code stealing credentials:** PR workflow has read-only `GITHUB_TOKEN`; no OIDC permission or cloud credentials are exposed.
- **Compromised action or mutable action ref:** third-party workflow actions are commit-pinned and updated through review.
- **Unscanned ARM64 image:** each architecture has an independently built local image and independent Trivy report; both are required by the gate.
- **Publishing from an unprotected branch:** workflow checks push/event and `github.ref_protected`, uses a restricted Environment, requires explicit enablement, and relies on cloud-side OIDC subject restrictions.
- **Mutable tag substitution:** Cosign signs and verifies the immutable digest; commit-based tags are metadata only.
- **Cloud credential theft:** federated OIDC tokens are short-lived; static provider keys are not used.
- **Vulnerability suppression:** ignore policy is empty by default; exceptions must be reviewable and time limited.
- **Cache/artifact poisoning:** trusted publisher should not consume artifacts or caches produced by untrusted PR workflows. Use isolated cache scope and hardened runners.
- **Base image drift / rebuild discrepancy:** rebuild after scan is documented as a gap; digest pinning and promotion by digest are needed for exact identity guarantees.

## Residual risks

Hosted-runner compromise, malicious approved source, upstream dependency compromise, stale advisory databases, registry-specific signature storage behavior, and cloud trust misconfiguration remain. Offline tests cannot validate these external trust boundaries.
