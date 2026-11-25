# Digest signing and verification

After registry push, form `registry/repository/image@sha256:<64-hex-digest>` from the builder's digest output. Cosign keyless signing obtains a short-lived certificate via GitHub OIDC; no private signing key is stored. Verification requires the expected workflow certificate identity and `https://token.actions.githubusercontent.com` as issuer. A tag-only reference, absent digest, wrong identity, wrong issuer, or failed verifier must stop release.

Check that the selected registry preserves Cosign signature OCI artifacts and that cleanup policies do not remove them. Offline fixtures validate input shapes only; they do not establish live signature validity.
