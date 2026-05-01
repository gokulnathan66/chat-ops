locals {
  lambda_zip = "${path.module}/../../dist/lambdas.zip"
}

resource "aws_lambda_function" "eval_runner" {
  function_name    = "${var.project}-${var.env}-eval-runner"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "rag_evaluator.handler"
  runtime          = "python3.12"
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)
  timeout          = 300
  memory_size      = 512

  environment {
    variables = {
      ENV                 = var.env
      PROJECT             = var.project
      CONVERSATIONS_TABLE = var.conversations_table
      EVALUATIONS_TABLE   = var.evaluations_table
    }
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_lambda_function" "golden_dataset_runner" {
  function_name    = "${var.project}-${var.env}-golden-dataset-runner"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "golden_dataset_runner.handler"
  runtime          = "python3.12"
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)
  timeout          = 300
  memory_size      = 512

  environment {
    variables = {
      ENV                  = var.env
      PROJECT              = var.project
      GOLDEN_RESULTS_TABLE = var.golden_results_table
      S3_BUCKET_NAME       = var.s3_bucket_name
    }
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_lambda_function" "pca_runner" {
  function_name    = "${var.project}-${var.env}-pca-runner"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "pca_runner.handler"
  runtime          = "python3.12"
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)
  timeout          = 300
  memory_size      = 512

  environment {
    variables = {
      ENV     = var.env
      PROJECT = var.project
    }
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_lambda_function" "qdrant_ingestion" {
  function_name    = "${var.project}-${var.env}-qdrant-ingestion"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "qdrant_ingestion.handler"
  runtime          = "python3.12"
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)
  timeout          = 300
  memory_size      = 512

  environment {
    variables = {
      ENV            = var.env
      PROJECT        = var.project
      S3_BUCKET_NAME = var.s3_bucket_name
    }
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}
