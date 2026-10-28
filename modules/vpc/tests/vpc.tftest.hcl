mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = {
      names = ["us-east-1a", "us-east-1b", "us-east-1c"]
    }
  }
  mock_data "aws_region" {
    defaults = { name = "us-east-1" }
  }
}

run "three_az_network_and_endpoints" {
  # apply here means a Terraform test apply against mock_provider only; no AWS API
  # calls or infrastructure creation are possible in this run.
  command = apply
  variables {
    name_prefix = "test"
    environment = "stage"
    vpc_cidr    = "10.50.0.0/16"
  }
  assert {
    condition     = length(output.availability_zones) == 3
    error_message = "Default AZ selection must create three AZs."
  }
  assert {
    condition     = length(output.public_subnet_ids) == 3 && length(output.private_subnet_ids) == 3
    error_message = "There must be one public and private subnet per selected AZ."
  }
  assert {
    condition     = length(output.nat_gateway_ids) == 3
    error_message = "There must be one NAT Gateway per AZ."
  }
  assert {
    condition     = aws_vpc_endpoint.s3.vpc_endpoint_type == "Gateway" && length(aws_vpc_endpoint.s3.route_table_ids) == 3
    error_message = "S3 must use a gateway endpoint associated with all private route tables."
  }
  assert {
    condition     = aws_vpc_endpoint.ecr_api.vpc_endpoint_type == "Interface" && aws_vpc_endpoint.ecr_api.private_dns_enabled && aws_vpc_endpoint.ecr_dkr.vpc_endpoint_type == "Interface" && aws_vpc_endpoint.ecr_dkr.private_dns_enabled
    error_message = "Both ECR endpoints must be private-DNS interface endpoints."
  }
  assert {
    condition     = aws_subnet.public["us-east-1a"].map_public_ip_on_launch && !aws_subnet.private["us-east-1a"].map_public_ip_on_launch
    error_message = "Public IP assignment must be enabled only for public subnets."
  }
  assert {
    condition     = one([for route in aws_route_table.private["us-east-1a"].route : route.nat_gateway_id]) == aws_nat_gateway.this["us-east-1a"].id
    error_message = "Each private route must use its same-AZ NAT Gateway."
  }
  assert {
    condition     = one([for route in aws_route_table.public["us-east-1a"].route : route.gateway_id]) == aws_internet_gateway.this.id
    error_message = "Public default routes must target the VPC Internet Gateway."
  }
  assert {
    condition     = length(aws_security_group.endpoints.ingress) == 1 && alltrue([for rule in aws_security_group.endpoints.ingress : rule.from_port == 443 && rule.to_port == 443])
    error_message = "ECR endpoint security group ingress must contain exactly one TCP/443 rule."
  }
  assert {
    condition     = alltrue([for rule in aws_security_group.endpoints.ingress : rule.protocol == "tcp"])
    error_message = "ECR endpoint security group ingress must use TCP."
  }
  assert {
    condition     = alltrue([for rule in aws_security_group.endpoints.ingress : length(rule.cidr_blocks) == 1 && contains(rule.cidr_blocks, "10.50.0.0/16")])
    error_message = "ECR endpoint security group ingress must be restricted to the trusted CIDRs."
  }
}

run "explicit_availability_zones" {
  command = plan
  variables {
    name_prefix             = "explicit"
    environment             = "dev"
    availability_zone_names = ["us-east-1a", "us-east-1c"]
  }
  assert {
    condition     = toset(output.availability_zones) == toset(["us-east-1a", "us-east-1c"])
    error_message = "Explicit AZ selection must be respected."
  }
}

run "reject_invalid_environment" {
  command = plan
  variables {
    name_prefix = "bad"
    environment = "qa"
  }
  expect_failures = [var.environment]
}

run "reject_insufficient_az_count" {
  command = plan
  variables {
    name_prefix             = "bad-count"
    environment             = "dev"
    availability_zone_count = 1
  }
  expect_failures = [var.availability_zone_count]
}

