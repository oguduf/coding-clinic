output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}
output "vpc_cidr" {
  description = "Configured VPC IPv4 CIDR."
  value       = aws_vpc.this.cidr_block
}
output "availability_zones" {
  description = "Availability Zones selected for this VPC."
  value       = local.selected_azs
}
output "public_subnet_ids" {
  description = "Public subnet IDs keyed by Availability Zone."
  value       = { for az, subnet in aws_subnet.public : az => subnet.id }
}
output "private_subnet_ids" {
  description = "Private subnet IDs keyed by Availability Zone."
  value       = { for az, subnet in aws_subnet.private : az => subnet.id }
}
output "internet_gateway_id" {
  description = "Internet Gateway ID."
  value       = aws_internet_gateway.this.id
}
output "nat_gateway_ids" {
  description = "NAT Gateway IDs keyed by Availability Zone."
  value       = { for az, nat in aws_nat_gateway.this : az => nat.id }
}
output "public_route_table_ids" {
  description = "Public route table IDs keyed by Availability Zone."
  value       = { for az, rt in aws_route_table.public : az => rt.id }
}
output "private_route_table_ids" {
  description = "Private route table IDs keyed by Availability Zone."
  value       = { for az, rt in aws_route_table.private : az => rt.id }
}
output "s3_endpoint_id" {
  description = "S3 gateway endpoint ID."
  value       = aws_vpc_endpoint.s3.id
}
output "ecr_api_endpoint_id" {
  description = "ECR API interface endpoint ID."
  value       = aws_vpc_endpoint.ecr_api.id
}
output "ecr_dkr_endpoint_id" {
  description = "ECR Docker Registry interface endpoint ID."
  value       = aws_vpc_endpoint.ecr_dkr.id
}
output "endpoint_security_group_id" {
  description = "Security group attached to the ECR interface endpoints."
  value       = aws_security_group.endpoints.id
}

