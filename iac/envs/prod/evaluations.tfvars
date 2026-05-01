# Cross-stack values injected by apply-evaluations Makefile target
s3_bucket_name       = ""
s3_bucket_arn        = ""
conversations_table  = ""
evaluations_table    = ""
hitl_table           = ""
golden_results_table = ""

eval_schedule   = "rate(1 hour)"
golden_schedule = "rate(24 hours)"
pca_schedule    = "rate(6 hours)"
