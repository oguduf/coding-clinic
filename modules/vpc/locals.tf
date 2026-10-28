data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  selected_azs  = var.availability_zone_names == null ? slice(data.aws_availability_zones.available.names, 0, min(var.availability_zone_count, length(data.aws_availability_zones.available.names))) : var.availability_zone_names
  az_count      = length(local.selected_azs)
  trusted_cidrs = coalesce(var.endpoint_trusted_cidrs, [var.vpc_cidr])
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Name        = var.name_prefix
  })
  az_map = { for index, az in local.selected_azs : az => index }
}

