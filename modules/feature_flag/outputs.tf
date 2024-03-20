output "enabled_path" {
  value = aws_ssm_parameter.enabled.name
}

output "context_path" {
  value = aws_ssm_parameter.context.name
}