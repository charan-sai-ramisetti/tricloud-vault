resource "aws_iam_role" "ec2_ssm_role" {
  name = "tricloud-ec2-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# S3 access for Ansible SSM connection plugin (file transfer)
resource "aws_iam_role_policy" "ansible_ssm_s3" {
  name = "ansible-ssm-s3"
  role = aws_iam_role.ec2_ssm_role.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ]
      Resource = [
        "arn:aws:s3:::tricloud-ansible-ssm",
        "arn:aws:s3:::tricloud-ansible-ssm/*"
      ]
    }]
  })
}

resource "aws_iam_instance_profile" "ssm_profile" {
  name = "tricloud-ssm-profile"
  role = aws_iam_role.ec2_ssm_role.name
}
