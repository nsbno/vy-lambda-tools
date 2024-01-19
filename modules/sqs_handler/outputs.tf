output "role_arn" {
  value = module.lambda.role_arn
}

output "role_name" {
  value = module.lambda.role_name
}

output "queue_url" {
  value = module.queue.queue_url
}

output "queue_arn" {
  value = module.queue.queue_arn
}