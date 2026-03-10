resource "aws_lb" "this" {

  load_balancer_type = "application"

  subnets         = var.subnet_ids
  security_groups = [var.security_group_id]

}

resource "aws_lb_target_group" "this" {

  port     = 8000
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  target_type = "instance"

  health_check {
    path                = "/"
    port                = "8000"
    protocol            = "HTTP"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

}

resource "aws_lb_listener" "http" {

  load_balancer_arn = aws_lb.this.arn

  port     = 80
  protocol = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }

}