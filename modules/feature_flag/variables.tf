variable "application_name" {
  description = "The name of the application"

  type = string
}

variable "flag_name" {
  description = "The name of the flag"

  type = string
}

variable "lambda_role_name" {
  description = "The name of the lambda role that will access the SSM parameters"

  type     = string
  nullable = true
  default  = null
}
