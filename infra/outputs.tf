output "api_url" {
  description = "Base URL of the API"
  value       = aws_apigatewayv2_stage.prod.invoke_url
}

output "ingest_endpoint" {
  description = "Endpoint to upload documents"
  value       = "${aws_apigatewayv2_stage.prod.invoke_url}/ingest"
}

output "query_endpoint" {
  description = "Endpoint to query documents"
  value       = "${aws_apigatewayv2_stage.prod.invoke_url}/query"
}

output "s3_bucket" {
  description = "S3 bucket for document uploads"
  value       = aws_s3_bucket.uploads.bucket
}

output "state_machine_arn" {
  description = "Step Functions state machine ARN"
  value       = aws_sfn_state_machine.ingestion.arn
}
