variable "role_name" {
  description = "Target role name."
  type        = string
  validation {
    condition     = length(var.role_name) >= 1 && length(var.role_name) <= 64 && can(regex("^[A-Za-z0-9+=,.@_-]+$", var.role_name))
    error_message = "role_name must use valid IAM role name characters and be 1-64 characters."
  }
}

variable "trusted_principal_arn" {
  description = "Exact source IAM role ARN trusted by this target role."
  type        = string
  validation {
    condition     = can(regex("^arn:aws(-us-gov|-cn)?:iam::[0-9]{12}:role/.+$", var.trusted_principal_arn))
    error_message = "trusted_principal_arn must identify a specific IAM role in an AWS account."
  }
}

variable "external_id" {
  description = "External ID injected via a secret source; never commit its value."
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.external_id) >= 2 && length(var.external_id) <= 1224
    error_message = "external_id must be 2-1224 characters."
  }
}

variable "environment" {
  description = "Environment label."
  type        = string
  validation {
    condition     = contains(["dev", "stage", "prod"], var.environment)
    error_message = "environment must be dev, stage, or prod."
  }
}

variable "max_session_duration" {
  description = "Maximum role session duration in seconds."
  type        = number
  default     = 3600
  validation {
    condition     = var.max_session_duration >= 3600 && var.max_session_duration <= 43200
    error_message = "IAM role maximum session duration must be 3600-43200 seconds."
  }
}

variable "policy_statements" {
  description = "Least-privilege statements; actions and resource ARNs are explicit."
  type = list(object({
    sid       = string
    actions   = list(string)
    resources = list(string)
  }))
  validation {
    condition = length(var.policy_statements) > 0 && alltrue([
      for s in var.policy_statements : length(s.actions) > 0 && length(s.resources) > 0 && alltrue([for action in s.actions : action != "*" && !endswith(action, ":*") && !contains(["iam:CreatePolicy", "iam:CreatePolicyVersion", "iam:SetDefaultPolicyVersion", "iam:AttachRolePolicy", "iam:PutRolePolicy", "iam:PassRole"], lower(action))]) && (!contains(s.resources, "*") || (length(s.actions) == 1 && contains(s.actions, "ecr:GetAuthorizationToken")))
    ])
    error_message = "Policy statements cannot grant wildcard/admin actions; only ECR GetAuthorizationToken may use Resource *."
  }
}

variable "permissions_boundary_arn" {
  description = "Optional IAM permissions boundary ARN."
  type        = string
  default     = null
  nullable    = true
}

variable "tags" {
  description = "Tags applied to the role and managed policy."
  type        = map(string)
  default     = {}
}
