# AWS ECR federation

Create an IAM OIDC provider and role through the organization's approved infrastructure process; this lab creates neither. Trust `token.actions.githubusercontent.com` with audience `sts.amazonaws.com` and a subject restricted to the repository's `production-publish` Environment and approved branch. Configure the role ARN and region as GitHub repository variables.

Grant ECR authorization and image layer/manifest push actions only against the named repository where AWS supports resource-level scope. The authorization token API may require `Resource: "*"`; keep all other actions repository scoped. No static AWS access key belongs in GitHub secrets.
