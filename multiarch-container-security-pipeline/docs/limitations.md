# Limitations

- No cloud authentication or cloud resource changes are performed.
- No images are pushed and no live Cosign signatures are created.
- Publication is gated and disabled unless an administrator configures the protected Environment, provider variables, cloud OIDC trust, and explicit enablement.
- Candidate scans use fresh online Trivy vulnerability data only when manually requested; baseline CI uses synthetic offline reports.
- The publisher rebuilds the same source revision after scan; mutable build inputs can yield different bytes. Exact artifact identity needs digest promotion from a trusted staging store.
- No SBOM or verified SLSA provenance is produced.
- Offline tests cannot prove provider-side federation, registry permissions, signature storage, or production runner isolation.
