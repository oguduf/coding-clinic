terraform {
  required_version = ">= 1.7.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  alias   = "source"
  region  = var.aws_region
  profile = var.source_profile
}

provider "aws" {
  alias   = "target"
  region  = var.aws_region
  profile = var.target_profile
}

module "target_role" {
  source                   = "../../modules/cross_account_role"
  providers                = { aws = aws.target }
  role_name                = var.target_role_name
  trusted_principal_arn    = "arn:aws:iam::${var.source_account_id}:role/${var.source_role_name}"
  external_id              = var.external_id
  environment              = "prod"
  max_session_duration     = var.session_duration
  policy_statements        = var.policy_statements
  tags                     = var.tags
  permissions_boundary_arn = var.permissions_boundary_arn
}

module "source_policy" {
  source           = "../../modules/source_assume_role_policy"
  providers        = { aws = aws.source }
  policy_name      = "prod-assume-approved-target-roles"
  source_role_name = var.source_role_name
  target_role_arns = ["arn:aws:iam::${var.target_account_id}:role/${var.target_role_name}"]
  tags             = var.tags
}

