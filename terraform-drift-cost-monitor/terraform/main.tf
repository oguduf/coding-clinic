terraform {
  required_version = ">= 1.10.5, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Partial backend configuration. Real values are supplied only by an
  # authorized live workflow; CI initializes with -backend=false.
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "example" {
  bucket = var.bucket_name

  tags = {
    Environment = var.environment
    Owner       = var.owner
    Project     = "drift-cost-monitor"
  }
}
