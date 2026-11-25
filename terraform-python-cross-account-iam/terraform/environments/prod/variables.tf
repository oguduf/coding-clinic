variable "source_profile" {
  type        = string
  description = "Named AWS CLI profile for the source account."
}

variable "target_profile" {
  type        = string
  description = "Named AWS CLI profile for the target account."
}

variable "aws_region" {
  type        = string
  description = "AWS region for provider operations."
}

variable "source_account_id" {
  type        = string
  description = "Synthetic/authorized source account ID."
  validation {
    condition     = can(regex("^[0-9]{12}$", var.source_account_id))
    error_message = "Must be a 12-digit account ID."
  }
}

variable "target_account_id" {
  type        = string
  description = "Synthetic/authorized target account ID."
  validation {
    condition     = can(regex("^[0-9]{12}$", var.target_account_id))
    error_message = "Must be a 12-digit account ID."
  }
}

variable "source_role_name" {
  type        = string
  description = "Source pipeline role name."
}

variable "target_role_name" {
  type        = string
  description = "Target role name."
}

variable "external_id" {
  type        = string
  sensitive   = true
  description = "Inject using TF_VAR_external_id from an approved secret manager."
}

variable "session_duration" {
  type        = number
  default     = 3600
  description = "Maximum target role session duration."
}

variable "policy_statements" {
  type = list(object({
    sid       = string
    actions   = list(string)
    resources = list(string)
  }))
  description = "Explicitly scoped target permissions."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Resource tags."
}
variable "permissions_boundary_arn" {
  type        = string
  description = "Pre-existing permissions boundary ARN approved for production."
}

