output "alb_sg_id" {
  value = aws_security_group.alb.id
}

output "backend_sg_id" {
  value = aws_security_group.backend.id
}
