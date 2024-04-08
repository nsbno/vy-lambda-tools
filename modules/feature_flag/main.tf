locals {
  base_name = "/applications/${var.application_name}/flags"

  flag_path = "${local.base_name}/${var.flag_name}"

  region = "eu-west-1"
}

resource "aws_ssm_parameter" "enabled" {
  name  = "${local.flag_path}/enabled"
  type  = "String"
  value = "null"

  lifecycle {
    ignore_changes = ["value"]
  }
}

resource "aws_ssm_parameter" "context" {
  name  = "${local.flag_path}/context"
  type  = "String"
  value = "null"

  lifecycle {
    ignore_changes = ["value"]
  }
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "allow_ssm" {
  statement {
    actions = [
      "ssm:GetParameters",
      "ssm:GetParameter",
      "ssm:GetParameterHistory",
      "ssm:GetParametersByPath"
    ]

    resources = [
      "arn:aws:ssm:${local.region}:${data.aws_caller_identity.current.account_id}:parameter${local.flag_path}/*",
      "arn:aws:ssm:${local.region}:${data.aws_caller_identity.current.account_id}:parameter${local.flag_path}"
    ]
  }
}

resource "aws_iam_role_policy" "allow_ssm" {
  count  = var.lambda_role_name != null ? 1 : 0

  role   = var.lambda_role_name
  policy = data.aws_iam_policy_document.allow_ssm.json
}