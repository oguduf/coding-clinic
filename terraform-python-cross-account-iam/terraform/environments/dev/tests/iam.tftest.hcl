mock_provider "aws" {}

run "target_role_has_explicit_external_id_trust" {
  command = plan
  module {
    source = "../../modules/cross_account_role"
  }
  variables {
    role_name             = "lab4-test-role"
    trusted_principal_arn = "arn:aws:iam::111122223333:role/pipeline"
    external_id           = "synthetic-test-external-id"
    environment           = "dev"
    policy_statements     = [{ sid = "ReadExample", actions = ["s3:GetObject"], resources = ["arn:aws:s3:::example-bucket/*"] }]
  }
  override_data {
    target = data.aws_iam_policy_document.trust
    values = {
      json = jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Effect    = "Allow"
          Principal = { AWS = "arn:aws:iam::111122223333:role/pipeline" }
          Action    = "sts:AssumeRole"
          Condition = { StringEquals = { "sts:ExternalId" = "synthetic-test-external-id" } }
        }]
      })
    }
  }
  override_data {
    target = data.aws_iam_policy_document.permissions
    values = {
      json = jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Effect   = "Allow"
          Action   = "s3:GetObject"
          Resource = "arn:aws:s3:::example-bucket/*"
        }]
      })
    }
  }
  assert {
    condition     = strcontains(aws_iam_role.target.assume_role_policy, "sts:ExternalId")
    error_message = "Trust policy must require an external ID."
  }
  assert {
    condition     = aws_iam_role.target.name == "lab4-test-role"
    error_message = "Role name must follow module input."
  }
}

run "source_policy_is_limited_to_approved_role_arns" {
  command = plan
  module {
    source = "../../modules/source_assume_role_policy"
  }
  variables {
    policy_name      = "source-assume-approved"
    source_role_name = "pipeline-role"
    target_role_arns = ["arn:aws:iam::444455556666:role/approved-target"]
  }
  override_data {
    target = data.aws_iam_policy_document.assume
    values = {
      json = jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Effect   = "Allow"
          Action   = "sts:AssumeRole"
          Resource = "arn:aws:iam::444455556666:role/approved-target"
        }]
      })
    }
  }
  assert {
    condition     = strcontains(aws_iam_policy.source.policy, "arn:aws:iam::444455556666:role/approved-target")
    error_message = "Source policy must target the approved role ARN."
  }
}

