# Security model

The CLI has no live mode. It reads local fixtures and pricing JSON and writes reports. The AWS adapter is a library interface for a future explicitly authorized integration; it is not called by the CLI or CI.

The management-side example grants only `organizations:ListAccounts` and `sts:AssumeRole` on the named member role. The member role grants only `ec2:DescribeRegions` and `ec2:DescribeVolumes`. `Describe*` actions generally require `Resource: "*"`; no mutation permission is included. The trust example uses placeholders and an organization condition. Replace placeholders only in an organization-controlled deployment after IAM review.

Credentials come from the standard SDK provider chain only when an external caller intentionally uses the adapter. STS credentials are temporary, passed in memory to a session, never persisted or logged. Do not put secrets in YAML, fixtures, tags, or reports. Account IDs, tags, volume IDs, and report files should be treated as sensitive metadata.

Reports are written through a temporary file and atomic replacement; POSIX mode is restricted to the owner where supported. On Windows, configure NTFS ACLs. `reports/` is ignored by Git. Cleanup plans say `manual_review_only`; there is no EC2 deletion call or destructive CLI option.

