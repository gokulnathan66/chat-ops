output "dashboard_name" {
  value = aws_cloudwatch_dashboard.llmops.dashboard_name
}

output "dashboard_url" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.llmops.dashboard_name}"
}
