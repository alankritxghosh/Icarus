targetScope = 'resourceGroup'

@description('Azure region for the canary application resources.')
param location string = resourceGroup().location

@description('Stable prefix used for canary resource names.')
@minLength(3)
param namePrefix string = 'icarus-canary'

@description('Existing Container Apps managed environment created by launch_canary_foundation.bicep.')
param environmentName string = '${namePrefix}-env'

@description('Existing user-assigned identity created by launch_canary_foundation.bicep.')
param identityName string = '${namePrefix}-identity'

@description('Existing Log Analytics workspace created by launch_canary_foundation.bicep.')
param workspaceName string = '${namePrefix}-logs'

@description('Azure Container Registry login server that holds the immutable launch candidate image.')
@minLength(1)
param acrLoginServer string

@description('Full pinned candidate image, preferably an ACR digest. Must not be latest.')
@minLength(7)
param candidateImage string

@description('Public GitHub OAuth client id for the isolated canary callback.')
@minLength(1)
param githubClientId string

@description('Incident response email for the canary action group.')
@minLength(3)
param incidentEmail string

@description('Key Vault secret URL for the configured Gemini serving key. The secret value is never supplied to this template.')
@secure()
param geminiApiKeyVaultUrl string

@description('Key Vault secret URL for the dedicated public-ingest GitHub token. The secret value is never supplied to this template.')
@secure()
param ghTokenKeyVaultUrl string

@description('Key Vault secret URL for the canary GitHub OAuth client secret. The secret value is never supplied to this template.')
@secure()
param githubClientSecretKeyVaultUrl string

@description('Optional Key Vault secret URL for PostHog product analytics. Empty disables analytics.')
@secure()
param posthogProjectTokenKeyVaultUrl string = ''

@description('Optional Key Vault secret URL for the analytics pseudonymization salt. Empty collapses analytics identity to anonymous and omits repository identity.')
@secure()
param icarusAnalyticsSaltKeyVaultUrl string = ''

var appName = '${namePrefix}-brain'
var requiredSecretRefs = [
  {
    envName: 'GEMINI_API_KEY'
    secretName: 'gemini-api-key'
    keyVaultUrl: geminiApiKeyVaultUrl
  }
  {
    envName: 'GH_TOKEN'
    secretName: 'gh-token'
    keyVaultUrl: ghTokenKeyVaultUrl
  }
  {
    envName: 'GITHUB_CLIENT_SECRET'
    secretName: 'github-client-secret'
    keyVaultUrl: githubClientSecretKeyVaultUrl
  }
]
var enabledOptionalSecretRefs = concat(
  !empty(posthogProjectTokenKeyVaultUrl) ? [
    {
      envName: 'POSTHOG_PROJECT_TOKEN'
      secretName: 'posthog-project-token'
      keyVaultUrl: posthogProjectTokenKeyVaultUrl
    }
  ] : [],
  !empty(icarusAnalyticsSaltKeyVaultUrl) ? [
    {
      envName: 'ICARUS_ANALYTICS_SALT'
      secretName: 'icarus-analytics-salt'
      keyVaultUrl: icarusAnalyticsSaltKeyVaultUrl
    }
  ] : []
)
var allSecretRefs = concat(requiredSecretRefs, enabledOptionalSecretRefs)
var secretEnv = [
  for item in allSecretRefs: {
    name: item.envName
    secretRef: item.secretName
  }
]
var runtimeEnv = concat([
  {
    name: 'ICARUS_REQUIRE_GITHUB_AUTH'
    value: '1'
  }
  {
    name: 'ICARUS_ALLOWED_HOSTS'
    value: '*'
  }
  {
    name: 'ICARUS_STORAGE_ROOT'
    value: '/data'
  }
  {
    name: 'ICARUS_GLOBAL_ASKS_PER_MINUTE'
    value: '120'
  }
  {
    name: 'ICARUS_GLOBAL_INVESTIGATIONS_PER_MINUTE'
    value: '12'
  }
  {
    name: 'ICARUS_GLOBAL_CONNECTS_PER_10_MINUTES'
    value: '30'
  }
  {
    name: 'ICARUS_MAX_CONCURRENT_WRITERS'
    value: '8'
  }
  {
    name: 'ICARUS_MAX_CONCURRENT_INGESTS'
    value: '2'
  }
  {
    name: 'GITHUB_CLIENT_ID'
    value: githubClientId
  }
], secretEnv)

resource environment 'Microsoft.App/managedEnvironments@2024-10-02-preview' existing = {
  name: environmentName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: identityName
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: workspaceName
}

resource app 'Microsoft.App/containerApps@2024-10-02-preview' = {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'Auto'
      }
      registries: [
        {
          server: acrLoginServer
          identity: identity.id
        }
      ]
      secrets: [
        for item in allSecretRefs: {
          name: item.secretName
          keyVaultUrl: item.keyVaultUrl
          identity: identity.id
        }
      ]
    }
    template: {
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      containers: [
        {
          name: 'icarus-brain'
          image: candidateImage
          env: runtimeEnv
          volumeMounts: [
            {
              volumeName: 'cache'
              mountPath: '/data'
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'cache'
          storageType: 'AzureFile'
          storageName: 'icarus-data'
        }
      ]
    }
  }
}

resource appDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${appName}-diagnostics'
  scope: app
  properties: {
    workspaceId: workspace.id
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${namePrefix}-incident-action-group'
  location: 'global'
  properties: {
    groupShortName: 'icaruscan'
    enabled: true
    emailReceivers: [
      {
        name: 'canary-incident-email'
        emailAddress: incidentEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

resource resourceGroupActivityAlert 'Microsoft.Insights/activityLogAlerts@2020-10-01' = {
  name: '${namePrefix}-resource-activity'
  location: 'global'
  properties: {
    enabled: true
    scopes: [
      resourceGroup().id
    ]
    condition: {
      allOf: [
        {
          field: 'category'
          equals: 'Administrative'
        }
      ]
    }
    actions: {
      actionGroups: [
        {
          actionGroupId: actionGroup.id
        }
      ]
    }
    description: 'Alert the canary incident contact on administrative activity in the isolated Icarus canary resource group.'
  }
}

output appName string = app.name
output appFqdn string = app.properties.configuration.ingress.fqdn
output actionGroupName string = actionGroup.name
