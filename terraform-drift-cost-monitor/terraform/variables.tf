variable "aws_region" {
  description = "AWS region for the example resource."
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "Placeholder name; set to the existing managed bucket in an authorized environment."
  type        = string
  default     = "replace-with-existing-managed-bucket"
}

variable "environment" {
  description = "Environment represented by this Terraform state."
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Owning team for the example resource."
  type        = string
  default     = "platform-team"
}
