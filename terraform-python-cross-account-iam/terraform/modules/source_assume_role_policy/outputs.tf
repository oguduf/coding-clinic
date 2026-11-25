output "policy_arn" {
  description = "Source identity policy ARN."
  value       = aws_iam_policy.source.arn
}

output "policy_json" {
  description = "Rendered source identity policy document."
  value       = data.aws_iam_policy_document.assume.json
}
