"""Azure canary acceptance is strict, read-only, and content-free."""

import copy
import unittest

from scripts.canary_control_plane import evaluate


def _healthy_snapshot():
    secret_names = (
        "GEMINI_API_KEY", "GH_TOKEN", "GITHUB_CLIENT_SECRET",
    )
    env = [
        {"name": "ICARUS_REQUIRE_GITHUB_AUTH", "value": "1"},
        {"name": "ICARUS_ALLOWED_HOSTS", "value": "*"},
        {"name": "ICARUS_STORAGE_ROOT", "value": "/data"},
        {"name": "ICARUS_GLOBAL_ASKS_PER_MINUTE", "value": "120"},
        {"name": "ICARUS_GLOBAL_INVESTIGATIONS_PER_MINUTE", "value": "12"},
        {"name": "ICARUS_GLOBAL_CONNECTS_PER_10_MINUTES", "value": "30"},
        {"name": "ICARUS_MAX_CONCURRENT_WRITERS", "value": "8"},
        {"name": "ICARUS_MAX_CONCURRENT_INGESTS", "value": "2"},
    ] + [
        {"name": name, "secretRef": f"secret-{index}"}
        for index, name in enumerate(secret_names)
    ] + [{"name": "GITHUB_CLIENT_ID", "value": "public-oauth-client-id"}]
    return {
        "app": {
            "id": "/subscriptions/s/resourceGroups/rg/providers/Microsoft.App/containerApps/app",
            "identity": {"type": "UserAssigned"},
            "properties": {
                "configuration": {
                    "activeRevisionsMode": "Single",
                    "ingress": {"external": True, "fqdn": "canary.example"},
                    "registries": [{
                        "server": "registry.example", "identity": "managed-identity-id",
                    }],
                    "secrets": [{
                        "name": f"secret-{index}",
                        "keyVaultUrl": f"https://vault.example/secrets/{name.casefold()}",
                        "identity": "/subscriptions/s/resourceGroups/rg/providers/"
                                    "Microsoft.ManagedIdentity/userAssignedIdentities/app",
                    } for index, name in enumerate(secret_names)],
                },
                "template": {
                    "scale": {"minReplicas": 1, "maxReplicas": 1},
                    "containers": [{
                        "image": "registry.example/icarus:abcdef1", "env": env,
                        "volumeMounts": [{"volumeName": "cache", "mountPath": "/data"}],
                    }],
                    "volumes": [{"name": "cache", "storageName": "canary-cache"}],
                },
            },
        },
        "environment": {"properties": {"appLogsConfiguration": {
            "destination": "log-analytics",
            "logAnalyticsConfiguration": {"customerId": "workspace-id"},
        }}},
        "environment_storages": [{"name": "canary-cache"}],
        "storage": {
            "id": "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/st",
            "minimumTlsVersion": "TLS1_2", "publicNetworkAccess": "Disabled",
            "networkRuleSet": {"defaultAction": "Deny"},
        },
        "file_service": {
            "shareDeleteRetentionPolicy": {"enabled": True, "days": 14},
        },
        "private_connections": [{
            "privateLinkServiceConnectionState": {"status": "Approved"},
        }],
        "locks": [{"level": "CanNotDelete"}],
        "activity_alerts": [{"enabled": True, "actions": {
            "actionGroups": [{"actionGroupId": "ag"}],
        }}],
        "diagnostics": [{"name": "canary-diagnostics", "properties": {
            "workspaceId": "/subscriptions/s/resourceGroups/rg/providers/"
                           "Microsoft.OperationalInsights/workspaces/logs",
            "metrics": [{"category": "AllMetrics", "enabled": True}],
        }}],
    }


class CanaryControlPlaneTests(unittest.TestCase):
    def test_hardened_snapshot_passes(self):
        self.assertEqual(evaluate(_healthy_snapshot()), [])

    def test_every_launch_boundary_fails_closed(self):
        cases = {
            "latest image": lambda s: s["app"]["properties"]["template"]["containers"][0].update(
                image="registry.example/icarus:latest"),
            "multiple replicas": lambda s: s["app"]["properties"]["template"]["scale"].update(
                maxReplicas=2),
            "password registry": lambda s: s["app"]["properties"]["configuration"]
                ["registries"][0].update(identity=None, passwordSecretRef="acr-password"),
            "raw secret": lambda s: s["app"]["properties"]["template"]["containers"][0]["env"].append(
                {"name": "GROQ_API_KEY", "secretRef": "legacy"}),
            "missing mount": lambda s: s["app"]["properties"]["template"]["containers"][0].update(
                volumeMounts=[]),
            "no logs": lambda s: s["environment"]["properties"].update(
                appLogsConfiguration={}),
            "tls 1.0": lambda s: s["storage"].update(minimumTlsVersion="TLS1_0"),
            "public storage": lambda s: s["storage"].update(publicNetworkAccess="Enabled"),
            "no soft delete": lambda s: s["file_service"].update(
                shareDeleteRetentionPolicy={"enabled": False, "days": 0}),
            "no private endpoint": lambda s: s.update(private_connections=[]),
            "no lock": lambda s: s.update(locks=[]),
            "no alert": lambda s: s.update(activity_alerts=[]),
            "no diagnostics": lambda s: s.update(diagnostics=[]),
            "diagnostics without workspace": lambda s: s["diagnostics"][0]
                ["properties"].update(workspaceId=None),
            "diagnostics without metrics": lambda s: s["diagnostics"][0]
                ["properties"].update(metrics=[]),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                snapshot = copy.deepcopy(_healthy_snapshot())
                mutate(snapshot)
                self.assertTrue(evaluate(snapshot), label)

    def test_secret_values_are_rejected_even_if_a_secret_ref_is_also_present(self):
        snapshot = _healthy_snapshot()
        item = next(item for item in snapshot["app"]["properties"]["template"]
                    ["containers"][0]["env"] if item["name"] == "GH_TOKEN")
        item["value"] = "must-not-be-here"
        self.assertIn(
            "runtime secret is not a secret reference: GH_TOKEN",
            evaluate(snapshot),
        )

    def test_platform_stored_secret_is_rejected_in_favour_of_key_vault(self):
        snapshot = _healthy_snapshot()
        secret = snapshot["app"]["properties"]["configuration"]["secrets"][0]
        secret["keyVaultUrl"] = None
        secret["identity"] = None
        self.assertTrue(any(
            "managed-identity Key Vault" in failure for failure in evaluate(snapshot)
        ))


if __name__ == "__main__":
    unittest.main()
