variable "source_role_name" {
  description = "Existing source pipeline IAM role receiving this policy."
  type        = string
}

variable "policy_name" {
  description = "Name of the source identity policy."
  type        = string
}

variable "target_role_arns" {
  description = "Explicit destination role ARNs authorized for assumption."
  type        = set(string)
  validation {
    condition     = length(var.target_role_arns) > 0 && alltrue([for arn in var.target_role_arns : can(regex("^arn:aws(-us-gov|-cn)?:iam::[0-9]{12}:role/.+$", arn))])
    error_message = "Provide one or more explicit IAM role ARNs; wildcards are not allowed."
  }
}

variable "tags" {
  description = "Tags applied to the policy."
  type        = map(string)
  default     = {}
}

