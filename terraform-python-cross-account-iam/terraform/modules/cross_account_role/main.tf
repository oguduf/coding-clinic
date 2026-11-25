data "aws_iam_policy_document" "trust" {
  statement {
    sid     = "TrustedPipelineWithExternalId"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.trusted_principal_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.external_id]
    }
  }
}

data "aws_iam_policy_document" "permissions" {
  dynamic "statement" {
    for_each = var.policy_statements
    content {
      sid       = statement.value.sid
      effect    = "Allow"
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
}

resource "aws_iam_role" "target" {
  name                 = var.role_name
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  max_session_duration = var.max_session_duration
  permissions_boundary = var.permissions_boundary_arn
  description          = "${var.environment} cross-account CI/CD role with external-ID trust."
  tags                 = merge(var.tags, { Environment = var.environment, ManagedBy = "Terraform" })
}

resource "aws_iam_policy" "target" {
  name        = "${var.role_name}-least-privilege"
  description = "Environment-scoped permissions for the cross-account CI/CD role."
  policy      = data.aws_iam_policy_document.permissions.json
  tags        = merge(var.tags, { Environment = var.environment, ManagedBy = "Terraform" })
}

resource "aws_iam_role_policy_attachment" "target" {
  role       = aws_iam_role.target.name
  policy_arn = aws_iam_policy.target.arn
}
