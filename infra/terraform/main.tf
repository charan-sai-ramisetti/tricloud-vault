module "aws_vpc" {
  source               = "./modules/aws/vpc"
  project_name         = var.project_name
  environment          = var.environment
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  availability_zones   = var.availability_zones
}

module "aws_sg" {
  source       = "./modules/aws/security-groups"
  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.aws_vpc.vpc_id
}

module "aws_ec2" {
  source            = "./modules/aws/ec2-backend"
  project_name      = var.project_name
  environment       = var.environment
  subnet_id         = module.aws_vpc.private_subnet_ids[0]
  security_group_id = module.aws_sg.backend_sg_id
  ami_id            = var.ami_id
  instance_type     = var.ec2_instance_type
}

module "aws_alb" {
  source             = "./modules/aws/alb"
  project_name       = var.project_name
  environment        = var.environment
  subnet_ids         = module.aws_vpc.public_subnet_ids
  security_group_id  = module.aws_sg.alb_sg_id
  target_instance_id = module.aws_ec2.instance_id
  vpc_id             = module.aws_vpc.vpc_id
}

module "aws_s3" {
  source       = "./modules/aws/s3-storage"
  project_name = var.project_name
  environment  = var.environment
}

module "azure_blob" {
  source       = "./modules/azure/blob-storage"
  project_name = var.project_name
  environment  = var.environment
  location     = var.azure_location
}

module "gcp_bucket" {
  source       = "./modules/gcp/storage-bucket"
  project_name = var.project_name
  environment  = var.environment
}
