resource "aws_dynamodb_table" "conversations" {
  name         = "${var.project}-${var.env}-${var.conversations_table}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "sk"

  attribute {
    name = "session_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }
  attribute {
    name = "last_updated_at"
    type = "S"
  }

  global_secondary_index {
    name            = "status-last_updated_at-index"
    hash_key        = "status"
    range_key       = "last_updated_at"
    projection_type = "ALL"
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_dynamodb_table" "evaluations" {
  name         = "${var.project}-${var.env}-${var.evaluations_table}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "sk"

  attribute {
    name = "session_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "eval_type"
    type = "S"
  }
  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "eval_type-created_at-index"
    hash_key        = "eval_type"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_dynamodb_table" "hitl_queue" {
  name         = "${var.project}-${var.env}-${var.hitl_table}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "queue_status"
    type = "S"
  }

  global_secondary_index {
    name            = "queue_status-sk-index"
    hash_key        = "queue_status"
    range_key       = "sk"
    projection_type = "ALL"
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_dynamodb_table" "golden_results" {
  name         = "${var.project}-${var.env}-${var.golden_results_table}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"
  range_key    = "question_id"

  attribute {
    name = "run_id"
    type = "S"
  }
  attribute {
    name = "question_id"
    type = "S"
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}
