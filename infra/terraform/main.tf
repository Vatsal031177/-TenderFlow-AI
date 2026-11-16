terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "eu-central-1" # Frankfurt (closest AWS region to Munich)
}

variable "environment" {
  default = "production"
}

resource "aws_vpc" "tendos_vpc" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_hostnames = true
  tags = {
    Name = "tenderflow-${var.environment}-vpc"
  }
}

resource "aws_db_instance" "postgres" {
  identifier             = "tenderflow-${var.environment}-pg"
  engine                 = "postgres"
  engine_version         = "16.3"
  instance_class         = "db.t4g.medium"
  allocated_storage      = 50
  db_name                = "tendos"
  username               = "tendos"
  manage_master_user_password = true
  skip_final_snapshot    = true
  publicly_accessible    = false
}

resource "aws_opensearch_domain" "catalog_search" {
  domain_name    = "tenderflow-${var.environment}-search"
  engine_version = "OpenSearch_2.13"

  cluster_config {
    instance_type  = "t3.small.search"
    instance_count = 1
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 20
  }
}

resource "aws_eks_cluster" "main" {
  name     = "tenderflow-${var.environment}-eks"
  role_arn = aws_iam_role.eks_cluster.arn

  vpc_config {
    subnet_ids = aws_subnet.private[*].id
  }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.tendos_vpc.id
  cidr_block        = cidrsubnet(aws_vpc.tendos_vpc.cidr_block, 8, count.index)
  availability_zone = "${var.aws_region}${count.index == 0 ? "a" : "b"}"
}

resource "aws_iam_role" "eks_cluster" {
  name = "tenderflow-${var.environment}-eks-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
    }]
  })
}
