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
  region = var.aws_region
  default_tags { tags = { Project = "multi-az-vpc-lab" } }
}

module "vpc" {
  source                  = "../../modules/vpc"
  name_prefix             = var.name_prefix
  environment             = "dev"
  vpc_cidr                = var.vpc_cidr
  availability_zone_count = var.availability_zone_count
  availability_zone_names = var.availability_zone_names
  subnet_newbits          = var.subnet_newbits
  endpoint_trusted_cidrs  = var.endpoint_trusted_cidrs
  tags                    = var.tags
}

