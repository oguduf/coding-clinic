data "aws_iam_policy_document" "assume" {
  statement {
    sid       = "AssumeApprovedTargetRoles"
    effect    = "Allow"
    actions   = ["sts:AssumeRole"]
    resources = sort(tolist(var.target_role_arns))
  }
}

resource "aws_iam_policy" "source" {
  name        = var.policy_name
  description = "Allow sts:AssumeRole only for explicitly approved target roles."
  policy      = data.aws_iam_policy_document.assume.json
  tags        = var.tags
}

resource "aws_iam_role_policy_attachment" "source" {
  role       = var.source_role_name
  policy_arn = aws_iam_policy.source.arn
}

