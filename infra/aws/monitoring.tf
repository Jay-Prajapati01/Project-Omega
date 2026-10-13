resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${local.name}-alb-5xx"
  alarm_description   = "The load balancer is returning server errors; inspect target health and ECS logs."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_ELB_5XX_Count"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }
  alarm_actions = var.alert_email == "" ? [] : [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_target_5xx" {
  alarm_name          = "${local.name}-api-target-5xx"
  alarm_description   = "The API is returning server errors; inspect API ECS logs and dependencies."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }
  alarm_actions = var.alert_email == "" ? [] : [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "web_target_5xx" {
  alarm_name          = "${local.name}-web-target-5xx"
  alarm_description   = "The website is returning server errors; inspect web ECS logs."
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.web.arn_suffix
  }
  alarm_actions = var.alert_email == "" ? [] : [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_cpu" {
  count               = var.deploy_services ? 1 : 0
  alarm_name          = "${local.name}-api-high-cpu"
  alarm_description   = "API CPU is high; check ECS capacity and request patterns."
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 85
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.api[0].name
  }
  alarm_actions = var.alert_email == "" ? [] : [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "worker_cpu" {
  count               = var.deploy_services ? 1 : 0
  alarm_name          = "${local.name}-worker-high-cpu"
  alarm_description   = "Worker CPU is high; inspect job failures and increase worker capacity if required."
  namespace           = "AWS/ECS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 90
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.worker[0].name
  }
  alarm_actions = var.alert_email == "" ? [] : [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "redis_cpu" {
  alarm_name          = "${local.name}-redis-high-cpu"
  alarm_description   = "ElastiCache CPU is elevated; inspect traffic and Redis capacity."
  namespace           = "AWS/ElastiCache"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.redis.id
  }
  alarm_actions = var.alert_email == "" ? [] : [aws_sns_topic.alerts.arn]
}
