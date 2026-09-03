targetScope = 'subscription'

@description('Dedicated resource group for the isolated launch canary.')
param resourceGroupName string = 'icarus-canary-rg'

@description('Azure region for every canary resource.')
param location string = 'centralindia'

@description('Stable prefix used for canary resource names.')
@minLength(3)
param namePrefix string = 'icarus-canary'

resource canaryResourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: {
    application: 'icarus'
    environment: 'canary'
    isolation: 'dedicated'
  }
}

module foundation './launch_canary_foundation.bicep' = {
  name: 'icarus-canary-foundation'
  scope: canaryResourceGroup
  params: {
    location: location
    namePrefix: namePrefix
  }
}

output resourceGroupName string = canaryResourceGroup.name
output containerAppsEnvironmentName string = foundation.outputs.containerAppsEnvironmentName
output keyVaultName string = foundation.outputs.keyVaultName
output managedIdentityName string = foundation.outputs.managedIdentityName
output storageAccountName string = foundation.outputs.storageAccountName
