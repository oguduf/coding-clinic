resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.common_tags, { Name = "${var.name_prefix}-vpc" })

  lifecycle {
    precondition {
      condition     = var.availability_zone_names == null ? length(data.aws_availability_zones.available.names) >= var.availability_zone_count : alltrue([for az in var.availability_zone_names : contains(data.aws_availability_zones.available.names, az)])
      error_message = "The configured region must provide the requested number of available AZs, and every explicitly selected AZ must be available."
    }
    precondition {
      condition     = pow(2, var.subnet_newbits) >= 2 * local.az_count && tonumber(split("/", var.vpc_cidr)[1]) + var.subnet_newbits <= 27
      error_message = "Subnet allocation does not have enough CIDR slots or leaves fewer than 32 addresses per subnet; adjust vpc_cidr, subnet_newbits, or AZ count."
    }
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.common_tags, { Name = "${var.name_prefix}-igw" })
}

resource "aws_subnet" "public" {
  for_each = local.az_map

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, var.subnet_newbits, each.value * 2)
  map_public_ip_on_launch = true
  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-public-${each.key}"
    Tier = "public"
  })
}

resource "aws_subnet" "private" {
  for_each = local.az_map

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, var.subnet_newbits, each.value * 2 + 1)
  map_public_ip_on_launch = false
  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-private-${each.key}"
    Tier = "private"
  })
}

resource "aws_eip" "nat" {
  for_each = local.az_map
  domain   = "vpc"
  tags     = merge(local.common_tags, { Name = "${var.name_prefix}-nat-eip-${each.key}" })
}

resource "aws_nat_gateway" "this" {
  for_each      = local.az_map
  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.key].id
  depends_on    = [aws_internet_gateway.this]
  tags          = merge(local.common_tags, { Name = "${var.name_prefix}-nat-${each.key}" })
}

resource "aws_route_table" "public" {
  for_each = local.az_map
  vpc_id   = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = merge(local.common_tags, { Name = "${var.name_prefix}-public-rt-${each.key}" })
}

resource "aws_route_table_association" "public" {
  for_each       = local.az_map
  subnet_id      = aws_subnet.public[each.key].id
  route_table_id = aws_route_table.public[each.key].id
}

resource "aws_route_table" "private" {
  for_each = local.az_map
  vpc_id   = aws_vpc.this.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[each.key].id
  }
  tags = merge(local.common_tags, { Name = "${var.name_prefix}-private-rt-${each.key}" })
}

resource "aws_route_table_association" "private" {
  for_each       = local.az_map
  subnet_id      = aws_subnet.private[each.key].id
  route_table_id = aws_route_table.private[each.key].id
}

