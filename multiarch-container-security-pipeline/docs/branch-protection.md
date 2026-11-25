# Branch protection and GitHub Environment checklist

An administrator must configure repository rulesets outside this codebase:

1. Protect `main` and release branches; require reviews, required CI, and prevent force pushes/deletion.
2. Create the `production-publish` GitHub Environment with required reviewers and deployment branch restrictions.
3. Keep the repository variable `PUBLISHING_ENABLED` unset or `false` by default. Set it to `true` only after cloud trust and policy review.
4. Configure cloud OIDC trust for the exact repository, protected ref, workflow identity, and Environment subject. Do not trust all branches.
5. Provide only registry host/repository and identity variables required by one provider.
6. Review changes to the publisher workflow as privileged changes.

The workflow checks `github.ref_protected`, but that value is meaningful only after branch rulesets exist. Naming a branch `main` alone does not protect it. Pull requests and forks never receive cloud publishing permissions. Manual dispatch requires explicit confirmation plus the same protected-ref, Environment, and cloud-side controls.
