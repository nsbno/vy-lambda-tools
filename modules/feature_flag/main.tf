locals {
  base_name = "/applications/${var.application_name}/flags"

  flag_path = "${local.base_name}/${var.flag_name}"
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

data "aws_iam_policy_document" "allow_ssm" {
  statement {
    actions = [
      "ssm:GetParameters",
      "ssm:GetParameter",
      "ssm:GetParameterHistory",
      "ssm:GetParametersByPath"
    ]

    resources = [
      aws_ssm_parameter.context.arn,
      aws_ssm_parameter.enabled.arn
    ]
  }
}

resource "aws_iam_role_policy" "allow_ssm" {
  role   = var.lambda_role_name
  policy = data.aws_iam_policy_document.allow_ssm.json
}