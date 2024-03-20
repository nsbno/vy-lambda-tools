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
