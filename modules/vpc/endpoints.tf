resource "aws_security_group" "endpoints" {
  name_prefix = "${var.name_prefix}-vpce-"
  description = "HTTPS ingress to ECR interface endpoints from trusted CIDRs."
  vpc_id      = aws_vpc.this.id
  ingress {
    description = "HTTPS from trusted client networks"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = local.trusted_cidrs
  }
  egress {
    description = "Return traffic and endpoint-initiated traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }
  tags = merge(local.common_tags, { Name = "${var.name_prefix}-vpce-sg" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  vpc_endpoint_type = "Gateway"
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  route_table_ids   = [for az in local.selected_azs : aws_route_table.private[az].id]
  tags              = merge(local.common_tags, { Name = "${var.name_prefix}-s3-vpce" })
}

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = aws_vpc.this.id
  vpc_endpoint_type   = "Interface"
  service_name        = "com.amazonaws.${data.aws_region.current.name}.ecr.api"
  subnet_ids          = [for az in local.selected_azs : aws_subnet.private[az].id]
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.common_tags, { Name = "${var.name_prefix}-ecr-api-vpce" })
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = aws_vpc.this.id
  vpc_endpoint_type   = "Interface"
  service_name        = "com.amazonaws.${data.aws_region.current.name}.ecr.dkr"
  subnet_ids          = [for az in local.selected_azs : aws_subnet.private[az].id]
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.common_tags, { Name = "${var.name_prefix}-ecr-dkr-vpce" })
}

data "aws_region" "current" {}

