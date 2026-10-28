variable "name_prefix" {
  description = "Stable prefix used in resource names and the Name tag."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]{0,39}$", var.name_prefix))
    error_message = "name_prefix must be 1-40 characters, start with a letter or digit, and contain only letters, digits, or hyphens."
  }
}

variable "environment" {
  description = "Deployment environment used for tagging."
  type        = string
  nullable    = false
  validation {
    condition     = contains(["dev", "stage", "prod"], var.environment)
    error_message = "environment must be one of: dev, stage, prod."
  }
}

variable "vpc_cidr" {
  description = "IPv4 CIDR for the VPC."
  type        = string
  default     = "10.0.0.0/16"
  nullable    = false
  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && try(tonumber(split("/", var.vpc_cidr)[1]) >= 16 && tonumber(split("/", var.vpc_cidr)[1]) <= 24, false)
    error_message = "vpc_cidr must be a valid IPv4 network between /16 and /24."
  }
}

variable "availability_zone_names" {
  description = "Optional explicit AZ names. If null, Terraform selects the first availability_zone_count available AZs in the configured provider region."
  type        = list(string)
  default     = null
  nullable    = true
  validation {
    condition     = var.availability_zone_names == null || (length(var.availability_zone_names) >= 2 && length(distinct(var.availability_zone_names)) == length(var.availability_zone_names))
    error_message = "When specified, availability_zone_names must contain at least two unique AZ names."
  }
}

variable "availability_zone_count" {
  description = "Number of AZs to select when availability_zone_names is null. Minimum two; defaults to three."
  type        = number
  default     = 3
  nullable    = false
  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count == floor(var.availability_zone_count) && var.availability_zone_count <= 8
    error_message = "availability_zone_count must be an integer from 2 through 8."
  }
}

variable "subnet_newbits" {
  description = "Additional prefix bits used to allocate each public/private subnet from vpc_cidr. Must leave at least five host bits."
  type        = number
  default     = 4
  nullable    = false
  validation {
    condition     = var.subnet_newbits >= 1 && var.subnet_newbits <= 8 && var.subnet_newbits == floor(var.subnet_newbits)
    error_message = "subnet_newbits must be an integer from 1 through 8."
  }
}

variable "endpoint_trusted_cidrs" {
  description = "CIDRs allowed to reach ECR interface endpoint ENIs on TCP/443. Defaults to the VPC CIDR."
  type        = list(string)
  default     = null
  nullable    = true
  validation {
    condition     = var.endpoint_trusted_cidrs == null || (length(var.endpoint_trusted_cidrs) > 0 && alltrue([for cidr in var.endpoint_trusted_cidrs : can(cidrnetmask(cidr)) && try(tonumber(split("/", cidr)[1]) > 0, false)]))
    error_message = "endpoint_trusted_cidrs must be non-empty IPv4 CIDRs narrower than 0.0.0.0/0."
  }
}

variable "tags" {
  description = "Additional tags applied to all taggable resources. Name, Environment, and ManagedBy are controlled by the module."
  type        = map(string)
  default     = {}
  nullable    = false
}

