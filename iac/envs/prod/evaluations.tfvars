# Cross-stack values injected by apply-evaluations Makefile target
s3_bucket_name       = ""
s3_bucket_arn        = ""
conversations_table  = ""
evaluations_table    = ""
hitl_table      = ""

eval_schedule = "rate(1 hour)"
pca_schedule  = "rate(6 hours)"
