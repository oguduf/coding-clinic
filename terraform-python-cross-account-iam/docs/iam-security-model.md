# IAM security model

The source identity policy authorizes calling `sts:AssumeRole` only for explicit target role ARNs. The target role trust policy is a resource-based policy that restricts who may assume the role and requires an external ID. The target permission policy defines what the session can do. A permissions boundary and an SCP constrain the maximum effective permissions; neither grants permissions. Resource policies are not created here.

Policies should use exact action and resource pairs. Some AWS APIs do not support resource-level constraints; any required wildcard should be isolated to that action and justified. This module permits only ECR `GetAuthorizationToken` as a narrowly validated wildcard-resource exception. Production examples are read-only, demonstrate a boundary, and call out manual approval outside Terraform.

CloudTrail can record AssumeRole events in a future authorized environment. Validate the resulting session identity and monitor unexpected role sessions. Static checks in this project are a review aid, not a full IAM simulator or Access Analyzer replacement.
