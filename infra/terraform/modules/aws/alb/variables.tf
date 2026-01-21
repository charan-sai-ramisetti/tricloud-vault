variable "project_name" {}
variable "environment" {}
variable "subnet_ids" {
  type = list(string)
}
variable "security_group_id" {}
variable "target_instance_id" {}
variable "vpc_id" {}
