# Supply-chain security notes

Use the platform-specific image reports as separate gate inputs. Keep vulnerability database freshness visible, fail on HIGH and CRITICAL findings, and review every exception for owner, justification, ticket, and expiration. The evaluator fails closed on malformed or absent reports.

Use the build output digest as the signed subject. Verify both expected certificate identity and the GitHub Actions OIDC issuer. Never sign a mutable tag as the artifact identity. Pin action commits and scanner/signing versions. Before operational use, pin base image digests and verify downloaded tool checksums.

Recommended follow-up: generate an SBOM per architecture, emit build provenance, verify provenance before promotion, and deploy by digest with admission policy. These are future enhancements and do not imply SLSA conformance here.
