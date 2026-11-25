# Azure Container Registry federation

An Azure administrator must configure a federated identity credential for the GitHub OIDC issuer and exact repository Environment subject, and grant the identity only the required ACR push role at the target registry. Supply client, tenant, subscription, registry name, and host through protected repository variables. Do not create Azure app registrations or federated credentials from this lab.
