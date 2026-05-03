terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "random_id" "suffix" {
  byte_length = 4
}

# S3 Bucket for document uploads
resource "aws_s3_bucket" "uploads" {
  bucket = "rag-uploads-${random_id.suffix.hex}"
}

# DynamoDB table for embeddings
resource "aws_dynamodb_table" "embeddings" {
  name         = "rag-embeddings-${random_id.suffix.hex}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "document"
  range_key    = "chunk_id"

  attribute {
    name = "document"
    type = "S"
  }

  attribute {
    name = "chunk_id"
    type = "S"
  }
}

# SNS Topic for notifications
resource "aws_sns_topic" "pipeline_complete" {
  name = "rag-pipeline-complete"
}

# IAM Role for Lambda functions
resource "aws_iam_role" "lambda_role" {
  name = "rag-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_permissions" {
  name = "rag-lambda-permissions"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.uploads.arn,
          "${aws_s3_bucket.uploads.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:Query",
          "dynamodb:BatchWriteItem"
        ]
        Resource = aws_dynamodb_table.embeddings.arn
      },
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution",
          "states:DescribeExecution"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = "sns:Publish"
        Resource = aws_sns_topic.pipeline_complete.arn
      }
    ]
  })
}

# IAM Role for Step Functions
resource "aws_iam_role" "sfn_role" {
  name = "rag-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "sfn_permissions" {
  name = "rag-sfn-permissions"
  role = aws_iam_role.sfn_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.extract.arn,
          aws_lambda_function.chunk.arn,
          aws_lambda_function.embed.arn,
          aws_lambda_function.index.arn,
          aws_lambda_function.notify.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda packaging
data "archive_file" "trigger" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/trigger"
  output_path = "${path.module}/../functions/trigger.zip"
}

data "archive_file" "extract" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/extract"
  output_path = "${path.module}/../functions/extract.zip"
}

data "archive_file" "chunk" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/chunk"
  output_path = "${path.module}/../functions/chunk.zip"
}

data "archive_file" "embed" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/embed"
  output_path = "${path.module}/../functions/embed.zip"
}

data "archive_file" "index" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/index"
  output_path = "${path.module}/../functions/index.zip"
}

data "archive_file" "query" {
  type        = "zip"
  source_dir  = "${path.module}/../functions/query"
  output_path = "${path.module}/../functions/query.zip"
}

data "archive_file" "notify" {
  type        = "zip"
  source_file = "${path.module}/../functions/notify/app.py"
  output_path = "${path.module}/../functions/notify.zip"
}

# Lambda: Trigger
resource "aws_lambda_function" "trigger" {
  filename         = "${path.module}/../functions/trigger.zip"
  function_name    = "rag-trigger"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 30
  source_code_hash = data.archive_file.trigger.output_base64sha256

  environment {
    variables = {
      STATE_MACHINE_ARN = aws_sfn_state_machine.ingestion.arn
      UPLOAD_BUCKET     = aws_s3_bucket.uploads.bucket
    }
  }
}

resource "aws_lambda_permission" "trigger_api" {
  statement_id  = "AllowAPIGatewayTrigger"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.trigger.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.rag_api.execution_arn}/*/*"
}

# Lambda: Extract
resource "aws_lambda_function" "extract" {
  filename         = "${path.module}/../functions/extract.zip"
  function_name    = "rag-extract"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 120
  memory_size      = 512
  source_code_hash = data.archive_file.extract.output_base64sha256
}

# Lambda: Chunk
resource "aws_lambda_function" "chunk" {
  filename         = "${path.module}/../functions/chunk.zip"
  function_name    = "rag-chunk"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 60
  source_code_hash = data.archive_file.chunk.output_base64sha256

  environment {
    variables = {
      CHUNK_SIZE    = "1000"
      CHUNK_OVERLAP = "200"
    }
  }
}

# Lambda: Embed
resource "aws_lambda_function" "embed" {
  filename         = "${path.module}/../functions/embed.zip"
  function_name    = "rag-embed"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 512
  source_code_hash = data.archive_file.embed.output_base64sha256

  environment {
    variables = {
      HF_API_KEY  = var.hf_api_key
      HF_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    }
  }
}

# Lambda: Index
resource "aws_lambda_function" "index" {
  filename         = "${path.module}/../functions/index.zip"
  function_name    = "rag-index"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 120
  source_code_hash = data.archive_file.index.output_base64sha256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.embeddings.name
    }
  }
}

# Lambda: Notify
resource "aws_lambda_function" "notify" {
  filename         = "${path.module}/../functions/notify.zip"
  function_name    = "rag-notify"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 30
  source_code_hash = data.archive_file.notify.output_base64sha256

  environment {
    variables = {
      SNS_TOPIC_ARN = aws_sns_topic.pipeline_complete.arn
    }
  }
}

# Lambda: Query
resource "aws_lambda_function" "query" {
  filename         = "${path.module}/../functions/query.zip"
  function_name    = "rag-query"
  role             = aws_iam_role.lambda_role.arn
  handler          = "app.handler"
  runtime          = "python3.12"
  timeout          = 120
  memory_size      = 512
  source_code_hash = data.archive_file.query.output_base64sha256

  environment {
    variables = {
      TABLE_NAME   = aws_dynamodb_table.embeddings.name
      HF_API_KEY   = var.hf_api_key
      GROQ_API_KEY = var.groq_api_key
      HF_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
      GROQ_MODEL   = "llama-3.1-8b-instant"
      TOP_K        = "5"
    }
  }
}

resource "aws_lambda_permission" "query_api" {
  statement_id  = "AllowAPIGatewayQuery"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.query.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.rag_api.execution_arn}/*/*"
}

# Step Functions State Machine
resource "aws_sfn_state_machine" "ingestion" {
  name     = "rag-ingestion-pipeline"
  role_arn = aws_iam_role.sfn_role.arn

  definition = jsonencode({
    Comment = "RAG Document Ingestion Pipeline"
    StartAt = "Extract"
    States = {
      Extract = {
        Type     = "Task"
        Resource = aws_lambda_function.extract.arn
        Next     = "Chunk"
        Retry = [{
          ErrorEquals      = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds  = 2
          MaxAttempts      = 3
          BackoffRate      = 2
        }]
      }
      Chunk = {
        Type     = "Task"
        Resource = aws_lambda_function.chunk.arn
        Next     = "Embed"
      }
      Embed = {
        Type     = "Task"
        Resource = aws_lambda_function.embed.arn
        Next     = "Index"
        Retry = [{
          ErrorEquals      = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
          IntervalSeconds  = 2
          MaxAttempts      = 3
          BackoffRate      = 2
        }]
      }
      Index = {
        Type     = "Task"
        Resource = aws_lambda_function.index.arn
        Next     = "Notify"
      }
      Notify = {
        Type     = "Task"
        Resource = aws_lambda_function.notify.arn
        End      = true
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }
}

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/states/rag-ingestion-pipeline"
  retention_in_days = 30
}

# API Gateway
resource "aws_apigatewayv2_api" "rag_api" {
  name          = "rag-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.rag_api.id
  name        = "prod"
  auto_deploy = true
}

# Integrations
resource "aws_apigatewayv2_integration" "trigger" {
  api_id                 = aws_apigatewayv2_api.rag_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.trigger.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "query" {
  api_id                 = aws_apigatewayv2_api.rag_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.query.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# Routes
resource "aws_apigatewayv2_route" "trigger" {
  api_id    = aws_apigatewayv2_api.rag_api.id
  route_key = "POST /ingest"
  target    = "integrations/${aws_apigatewayv2_integration.trigger.id}"
}

resource "aws_apigatewayv2_route" "query" {
  api_id    = aws_apigatewayv2_api.rag_api.id
  route_key = "POST /query"
  target    = "integrations/${aws_apigatewayv2_integration.query.id}"
}
