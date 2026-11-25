# Limitations

- This code-only lab did not access AWS accounts or scan live resources.
- It did not create, modify, or delete AWS resources.
- CLI and CI operate only on synthetic fixtures; the AWS adapter is not invoked.
- Sample account and volume identifiers are fabricated examples and are not usable AWS resources.
- Pricing values are illustrative only. Actual prices and discounts vary by region and agreement.
- Volume age comes from `CreateTime`; it does not establish how long the volume has been unattached.
- A currently `available` volume may still be needed for recovery, retention, or an application workflow.
- Review recommendations are not approval to delete. No deletion operation is implemented.
- Live discovery results can change between runs. Historical attachment state requires another source.
- No actual savings or 85% coverage target is claimed unless a measured run is documented.

