#!/usr/bin/env python3
"""Read-only acceptance check for the Azure launch-canary control plane.

The command queries resource metadata only. It never asks Azure CLI to show
secrets, never prints resource JSON, and performs no create/update/delete. Its
fixed PASS/FAIL output is safe to retain as launch evidence.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


REQUIRED_VALUES = {
    "ICARUS_REQUIRE_GITHUB_AUTH": "1",
    "ICARUS_ALLOWED_HOSTS": "*",
    "ICARUS_STORAGE_ROOT": "/data",
    "ICARUS_GLOBAL_ASKS_PER_MINUTE": "120",
    "ICARUS_GLOBAL_INVESTIGATIONS_PER_MINUTE": "12",
    "ICARUS_GLOBAL_CONNECTS_PER_10_MINUTES": "30",
    "ICARUS_MAX_CONCURRENT_WRITERS": "8",
    "ICARUS_MAX_CONCURRENT_INGESTS": "2",
}
REQUIRED_SECRET_REFS = {
    "GEMINI_API_KEY", "GH_TOKEN", "GITHUB_CLIENT_SECRET",
}
REQUIRED_PRESENT = {"GITHUB_CLIENT_ID"}  # OAuth client ids are public identifiers.
OPTIONAL_SECRET_REFS = {"POSTHOG_PROJECT_TOKEN", "ICARUS_ANALYTICS_SALT"}
FORBIDDEN_ENV = {"GROQ_API_KEY", "GEMINI_PAID_API_KEY", "ICARUS_SYNC_CONNECT"}


def _nested(value, *keys, default=None):
    for key in keys:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
    return default if value is None else value


def evaluate(snapshot):
    """Return fixed, content-free failure labels for one collected snapshot."""
    failures = []
    app = snapshot["app"]
    environment = snapshot["environment"]
    storage = snapshot["storage"]
    file_service = snapshot["file_service"]

    configuration = _nested(app, "properties", "configuration", default={})
    template = _nested(app, "properties", "template", default={})
    containers = template.get("containers") or []
    if len(containers) != 1:
        failures.append("runtime must have exactly one application container")
        container = {}
    else:
        container = containers[0]
    image = str(container.get("image") or "")
    if not image or image.casefold().endswith(":latest"):
        failures.append("runtime image is not pinned to an immutable candidate tag")
    if str(configuration.get("activeRevisionsMode", "")).casefold() != "single":
        failures.append("active revision mode is not single")
    identity_type = str(_nested(app, "identity", "type", default=""))
    if "assigned" not in identity_type.casefold():
        failures.append("runtime has no managed identity")
    registries = configuration.get("registries") or []
    if not registries or any(
            not item.get("identity") or item.get("passwordSecretRef")
            for item in registries):
        failures.append("container registry pull is not managed-identity only")
    scale = template.get("scale") or {}
    if scale.get("minReplicas") != 1 or scale.get("maxReplicas") != 1:
        failures.append("runtime is not pinned to one warm replica")
    ingress = configuration.get("ingress") or {}
    if ingress.get("external") is not True or not ingress.get("fqdn"):
        failures.append("HTTPS ingress is not externally addressable")

    env = {item.get("name"): item for item in container.get("env") or []}
    secret_definitions = {
        item.get("name"): item for item in configuration.get("secrets") or []
    }
    for name, expected in REQUIRED_VALUES.items():
        if str((env.get(name) or {}).get("value")) != expected:
            failures.append(f"runtime value missing or wrong: {name}")
    secret_env_names = REQUIRED_SECRET_REFS | (OPTIONAL_SECRET_REFS & set(env))
    for name in secret_env_names:
        item = env.get(name) or {}
        reference = item.get("secretRef")
        if not reference or item.get("value") not in (None, ""):
            failures.append(f"runtime secret is not a secret reference: {name}")
            continue
        definition = secret_definitions.get(reference) or {}
        if not str(definition.get("keyVaultUrl") or "").startswith("https://") \
                or not definition.get("identity"):
            failures.append(f"runtime secret is not backed by managed-identity Key Vault: {name}")
    for name in REQUIRED_PRESENT:
        item = env.get(name) or {}
        if not item.get("value") and not item.get("secretRef"):
            failures.append(f"required runtime identifier is missing: {name}")
    for name in sorted(FORBIDDEN_ENV & set(env)):
        failures.append(f"forbidden serving variable is present: {name}")

    mounts = container.get("volumeMounts") or []
    if not any(m.get("volumeName") == "cache" and m.get("mountPath") == "/data"
               for m in mounts):
        failures.append("durable cache is not mounted at /data")
    volumes = template.get("volumes") or []
    storage_name = next((v.get("storageName") for v in volumes
                         if v.get("name") == "cache"), None)
    if not storage_name:
        failures.append("durable cache volume has no environment storage binding")
    env_storages = snapshot["environment_storages"]
    if storage_name and not any(item.get("name") == storage_name
                                for item in env_storages):
        failures.append("environment storage binding is missing")

    logs = _nested(environment, "properties", "appLogsConfiguration", default={})
    if str(logs.get("destination", "")).casefold() != "log-analytics" \
            or not _nested(logs, "logAnalyticsConfiguration", "customerId"):
        failures.append("Container Apps environment is not connected to Log Analytics")

    if storage.get("minimumTlsVersion") != "TLS1_2":
        failures.append("storage minimum TLS is not TLS1_2")
    if str(storage.get("publicNetworkAccess", "")).casefold() != "disabled":
        failures.append("storage public network access is not disabled")
    if str(_nested(storage, "networkRuleSet", "defaultAction", default="")).casefold() \
            != "deny":
        failures.append("storage network default action is not deny")
    retention = file_service.get("shareDeleteRetentionPolicy") or {}
    if retention.get("enabled") is not True or int(retention.get("days") or 0) < 7:
        failures.append("Azure Files soft delete is not enabled for at least 7 days")
    private_connections = snapshot["private_connections"]
    if not any(str(_nested(item, "privateLinkServiceConnectionState", "status",
                           default="")).casefold() == "approved"
               for item in private_connections):
        failures.append("storage has no approved private endpoint connection")

    locks = snapshot["locks"]
    if not any(str(item.get("level", "")).casefold() == "cannotdelete"
               for item in locks):
        failures.append("resource group has no CanNotDelete lock")
    alerts = snapshot["activity_alerts"]
    if not any(_activity_alert_has_action_group(item) for item in alerts):
        failures.append("resource group has no enabled activity-log alert destination")
    diagnostics = snapshot["diagnostics"]
    if not any(_diagnostic_routes_to_workspace(item) for item in diagnostics):
        failures.append("container app has no workspace-backed metric diagnostic setting")
    return failures


def _activity_alert_has_action_group(item):
    if item.get("enabled") is not True:
        return False
    action_groups = _nested(item, "actions", "actionGroups", default=None)
    if action_groups is None:
        action_groups = item.get("actions")
    return any(group.get("actionGroupId") for group in action_groups or []
               if isinstance(group, dict))


def _diagnostic_routes_to_workspace(item):
    workspace_id = item.get("workspaceId") or _nested(item, "properties", "workspaceId")
    metrics = item.get("metrics") or _nested(item, "properties", "metrics", default=[])
    return bool(workspace_id) and any(
        str(metric.get("category", "")).casefold() == "allmetrics"
        and metric.get("enabled") is True
        for metric in metrics or []
        if isinstance(metric, dict)
    )


def _az(label, *args):
    command = ["az", *args, "--only-show-errors", "--output", "json"]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Azure query failed: {label}")
    try:
        return json.loads(result.stdout or "null")
    except ValueError as exc:
        raise RuntimeError(f"Azure query returned invalid JSON: {label}") from exc


def collect(resource_group, app_name, environment_name, storage_name):
    app = _az("container app", "containerapp", "show", "-g", resource_group,
              "-n", app_name)
    environment = _az("Container Apps environment", "containerapp", "env", "show",
                      "-g", resource_group, "-n", environment_name)
    storage = _az("storage account", "storage", "account", "show",
                  "-g", resource_group, "-n", storage_name)
    storage_id = storage.get("id")
    app_id = app.get("id")
    if not storage_id or not app_id:
        raise RuntimeError("Azure query omitted a required resource id")
    diagnostics = _az(
        "diagnostic settings", "monitor", "diagnostic-settings", "list",
        "--resource", app_id)
    if isinstance(diagnostics, dict):
        diagnostics = diagnostics.get("value", [])
    if not isinstance(diagnostics, list):
        raise RuntimeError("Azure query returned unexpected diagnostic settings")
    return {
        "app": app,
        "environment": environment,
        "environment_storages": _az(
            "environment storage", "containerapp", "env", "storage", "list",
            "-g", resource_group, "-n", environment_name),
        "storage": storage,
        "file_service": _az(
            "file-service policy", "storage", "account", "file-service-properties",
            "show", "-g", resource_group, "-n", storage_name),
        "private_connections": _az(
            "private endpoints", "network", "private-endpoint-connection", "list",
            "--id", storage_id),
        "locks": _az("resource locks", "lock", "list", "-g", resource_group),
        "activity_alerts": _az(
            "activity alerts", "monitor", "activity-log", "alert", "list",
            "-g", resource_group),
        "diagnostics": diagnostics,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--storage-account", required=True)
    args = parser.parse_args()
    try:
        failures = evaluate(collect(
            args.resource_group, args.app, args.environment, args.storage_account))
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        print(f"CONTROL PLANE FAILED: {exc}", file=sys.stderr)
        return 1
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print("CONTROL PLANE PASSED: all launch invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
