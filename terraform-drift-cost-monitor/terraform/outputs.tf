output "bucket_name" {
  description = "Name of the example Terraform-managed bucket."
  value       = aws_s3_bucket.example.bucket
}
