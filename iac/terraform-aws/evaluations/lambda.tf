resource "aws_lambda_function" "eval_runner" {
  function_name = "eval_runner"
  role          = aws_iam_role.eval_lambda_exec.arn
  handler       = "eval_runner.handler"
  runtime       = "python3.13"
  timeout       = 300
  memory_size   = 512

  filename         = "dist/lambdas.zip"
  source_code_hash = filebase64sha256("dist/lambdas.zip")

  environment {
    variables = {
      CONVERSATIONS_TABLE = var.conversations_table
      EVALUATIONS_TABLE   = var.evaluations_table
      HITL_TABLE          = var.hitl_table
      INACTIVITY_MINUTES  = tostring(var.inactivity_minutes)
      RAG_THRESHOLD       = tostring(var.rag_threshold)
      HITL_THRESHOLD      = tostring(var.hitl_threshold)
    }
  }
}

resource "aws_lambda_function" "golden_dataset_runner" {
  function_name = "golden_dataset_runner"
  role          = aws_iam_role.eval_lambda_exec.arn
  handler       = "golden_dataset_runner.handler"
  runtime       = "python3.13"
  timeout       = 600
  memory_size   = 1024

  filename         = "dist/lambdas.zip"
  source_code_hash = filebase64sha256("dist/lambdas.zip")

  environment {
    variables = {
      GOLDEN_RESULTS_TABLE  = var.golden_results_table
      GOLDEN_PASS_THRESHOLD = tostring(var.golden_pass_threshold)
      S3_BUCKET_NAME        = var.s3_bucket_name
    }
  }
}

resource "aws_lambda_function" "pca_runner" {
  function_name = "pca_runner"
  role          = aws_iam_role.eval_lambda_exec.arn
  handler       = "pca.handler"
  runtime       = "python3.13"
  timeout       = 300
  memory_size   = 512

  filename         = "dist/lambdas.zip"
  source_code_hash = filebase64sha256("dist/lambdas.zip")

  environment {
    variables = {
      CONVERSATIONS_TABLE = var.conversations_table
      EVALUATIONS_TABLE   = var.evaluations_table
      INACTIVITY_MINUTES  = tostring(var.inactivity_minutes)
    }
  }
}
