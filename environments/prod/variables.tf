variable "aws_region" {
  description = "AWS region configured on the provider."
  type        = string
  default     = "us-east-2"
}
variable "name_prefix" {
  description = "Resource naming prefix."
  type        = string
  default     = "clinic-prod"
}
variable "vpc_cidr" {
  description = "VPC IPv4 CIDR."
  type        = string
  default     = "10.30.0.0/16"
}
variable "availability_zone_count" {
  description = "AZ count when explicit names are unset."
  type        = number
  default     = 3
}
variable "availability_zone_names" {
  description = "Optional explicit AZ names."
  type        = list(string)
  default     = null
}
variable "subnet_newbits" {
  description = "Additional subnet prefix bits."
  type        = number
  default     = 4
}
variable "endpoint_trusted_cidrs" {
  description = "CIDRs allowed HTTPS access to ECR endpoints; null uses VPC CIDR."
  type        = list(string)
  default     = null
}
variable "tags" {
  description = "Additional tags."
  type        = map(string)
  default     = { CostCenter = "engineering-lab" }
}

