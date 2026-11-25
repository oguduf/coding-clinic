# Limitations

- No AWS account was accessed and no credentials were configured.
- No IAM role or policy was created or modified.
- No live STS AssumeRole or caller identity request was made.
- No end-to-end cross-account authorization was tested.
- No Terraform apply/destroy or CI deployment was run.
- The policy validator performs offline structural checks only; AWS IAM semantics and organization guardrails require further review.
- Terraform native mock tests require Terraform 1.7 or newer and validate planned objects, not AWS behavior.
