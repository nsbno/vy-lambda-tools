variable "name" {
  description = "The name of this handler"

  type = string
}

variable "artifact" {
  description = "The artifact to deploy"

  type = map(any)
}

variable "handler" {
  description = "Reference to the handler"

  type = string
}

variable "python_version" {
  description = "The version of python to use"

  type = string
}

variable "lambda_memory" {
  description = "The amount of memory to allocate to the lambda function"
  type        = number
}

variable "lambda_timeout" {
  description = "The amount of time to allow the lambda function to run"
  type        = number
}

variable "environment_variables" {
  description = "The environment to deploy to"

  type = map(string)
  default = {}
}