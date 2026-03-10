output "instance_id" {
  value = aws_instance.this.id
}
output "iam_instance_profile" {
  value = aws_iam_instance_profile.ssm_profile.name
}
