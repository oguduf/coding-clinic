output "role_arn" {
  description = "Target IAM role ARN."
  value       = aws_iam_role.target.arn
}

output "role_name" {
  description = "Target IAM role name."
  value       = aws_iam_role.target.name
}

output "permission_policy_arn" {
  description = "Managed least-privilege policy ARN."
  value       = aws_iam_policy.target.arn
}
