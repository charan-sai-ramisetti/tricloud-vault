project_name = "tricloud-vault"
environment  = "dev"

aws_region = "ap-south-1"

vpc_cidr = "10.0.0.0/16"

public_subnet_cidrs = [
  "10.0.1.0/24",
  "10.0.2.0/24"
]

private_subnet_cidrs = [
  "10.0.101.0/24",
  "10.0.102.0/24"
]

availability_zones = [
  "ap-south-1a",
  "ap-south-1b"
]

ami_id            = "ami-0f5ee92e2d63afc18"
ec2_instance_type = "t3.micro"

azure_location  = "centralindia"

gcp_project_id = "main-guild-468105-v3"
gcp_region     = "asia-south1"
