# Coding Clinic

This repository contains the Terraform drift detection and cost monitoring lab in [`terraform-drift-cost-monitor/`](terraform-drift-cost-monitor/).

The lab compares Terraform-managed infrastructure with refresh-only plans, estimates configured monthly cost with Infracost, and supports optional Slack notifications. Its scheduled workflow is disabled for live AWS access unless explicitly enabled through repository configuration.

See the [lab README](terraform-drift-cost-monitor/README.md) for architecture, setup, safety controls, local validation, and examples. Repository CI and the scheduled workflow are kept together in [`.github/workflows/`](.github/workflows/).