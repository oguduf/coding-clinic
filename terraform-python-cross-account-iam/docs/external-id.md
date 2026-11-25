# External ID

An external ID is a caller-provided value checked by a target role trust policy through `sts:ExternalId`. It helps a third-party service avoid a confused-deputy problem when many customers trust the same vendor principal. The value must be unique to the integration/customer relationship and supplied to STS at assumption time.

It is not a password, access key, or proof of identity. It does not make a wildcard principal safe and does not replace a specific trusted principal, source-side permission, or secret handling. This project takes it as sensitive Terraform input and Python input; examples use only synthetic placeholders and CLI reports redact it.
