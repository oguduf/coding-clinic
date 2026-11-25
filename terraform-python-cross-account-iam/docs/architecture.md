# Architecture and trust flow

The pipeline uses its source-account identity to call STS `AssumeRole` on a small allowlist of destination role ARNs. The destination role trust policy accepts the exact pipeline role ARN and requires a configured `sts:ExternalId`. After assumption, the role's separately attached permission policy limits access to approved resources. Dev, stage, and prod use the same modules with separate target accounts and policies.

Successful access requires source identity authorization, matching target trust, target role permissions, and no denying session policy, permissions boundary, SCP, or resource policy. Terraform describes these relationships but this repository does not deploy them.
