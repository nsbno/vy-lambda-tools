variable "application_name" {
  type        = string
  description = "The name of the application"
}

variable "flag_name" {
  type        = string
  description = "The name of the flag"
}

variable "lambda_role_name" {
  type        = string
  description = "The name of the lambda role that will access the SSM parameters"
}