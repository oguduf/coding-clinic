# Google Artifact Registry federation

Use Workload Identity Federation and a narrowly scoped provider condition for repository, protected ref, and GitHub Environment. Grant the mapped service account Artifact Registry Writer only on the selected repository. Use the short-lived identity token; do not use service-account JSON keys.

Artifact Registry is the preferred current Google registry service. Legacy Google Container Registry (GCR) is a separate older service and should not be conflated with Artifact Registry.
