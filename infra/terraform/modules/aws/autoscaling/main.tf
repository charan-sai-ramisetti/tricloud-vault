resource "aws_launch_template" "backend" {

  name_prefix = "${var.project_name}-${var.environment}-lt"

  image_id      = var.ami_id
  instance_type = var.instance_type

  vpc_security_group_ids = [var.security_group_id]

  iam_instance_profile {
    name = var.instance_profile
  }

  user_data = base64encode(file("${path.module}/user_data.sh"))

}
resource "aws_autoscaling_group" "backend" {

  name = "${var.project_name}-${var.environment}-asg"

  min_size         = 1
  max_size         = 3
  desired_capacity = 1

  vpc_zone_identifier = var.private_subnets

  launch_template {
    id      = aws_launch_template.backend.id
    version = "$Latest"
  }

  target_group_arns = [var.target_group_arn]

  health_check_type = "ELB"

}