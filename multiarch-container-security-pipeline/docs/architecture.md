# Architecture and artifact flow

Validation and publication are separate trust zones. Pull requests run tests and static checks with read-only repository scope. Candidate image scans are a separate, manually confirmed workflow. The publication workflow requires an explicit repository variable, protected branch status, and protected GitHub Environment. Only its reusable publisher receives `id-token: write`.

The scan job builds one local image per platform, then runs Trivy independently on each. Both report artifacts are required by the gate. Missing or malformed output is a failure. The publisher builds an OCI index only after a successful gate, captures its digest, signs that digest with keyless Cosign, and verifies identity and issuer.

The publisher rebuilds after scanning, so the scanned candidates and final artifact are not byte-identical evidence. Pin all build inputs and consider a trusted staging registry plus digest promotion when policy requires scanning the exact artifact that is released.
