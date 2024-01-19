module "lambda" {
  source = "github.com/nsbno/terraform-aws-lambda?ref=0.2.0"

  name = var.name

  artifact_type = "s3"
  artifact      = var.artifact

  runtime = "python${var.python_version}"
  handler = var.handler

  memory  = var.lambda_memory
  timeout = var.lambda_timeout

  environment_variables = var.environment_variables
}

module "queue" {
  source = "github.com/nsbno/terraform-aws-queue?ref=0.0.5"

  name               = var.name
  visibility_timeout = var.lambda_timeout
}

data "aws_iam_policy_document" "allow_sqs_queue" {
  statement {
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
    ]

    resources = [
      module.queue.queue_arn
    ]
  }
}

resource "aws_iam_role_policy" "allow_sqs_queue" {
  role   = module.lambda.role_name
  policy = data.aws_iam_policy_document.allow_sqs_queue.json
  name   = "AllowReceiveFromSQS"
}

resource "aws_lambda_event_source_mapping" "queue" {
  event_source_arn = module.queue.queue_arn
  function_name    = module.lambda.function_name

  function_response_types = ["ReportBatchItemFailures"]
}
