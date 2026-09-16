from __future__ import annotations

import hashlib
import json
from typing import Any


MATURITY = ("experimental", "community", "candidate", "standard")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def technology_evidence_statement(extension: dict[str, Any]) -> dict[str, Any]:
    """Return the bounded evidence statement signed by a conformance receipt.

    The adoption/public-record reference itself is deliberately excluded so the
    digest is stable before and after binding the receipt back onto the extension.
    Unknown extension metadata also stays outside the trust decision: older cores
    preserve it, but cannot accidentally bless evidence fields they do not know.
    """
    item = normalize_technology_extension(extension)
    return {
        "version": 1,
        "extensionId": item["id"],
        "declaredMaturity": item["maturity"],
        "requestedCore": bool(item["requestedCore"]),
        "mandatoryCore": bool(item["mandatoryCore"]),
        "publicSpec": bool(item["publicSpec"]),
        "conformanceTests": bool(item["conformanceTests"]),
        "interoperabilityEvidence": bool(item["interoperabilityEvidence"]),
        "fallbackDefined": bool(item["fallbackDefined"]),
        "backwardCompatible": bool(item["backwardCompatible"]),
        "unknownPreservationTested": bool(item["unknownPreservationTested"]),
        "productionDeployments": int(item["productionDeployments"]),
        "dependencies": {
            "mandatoryVendor": str(item["dependencies"].get("mandatoryVendor", "")),
            "cloudRequired": bool(item["dependencies"].get("cloudRequired")),
            "aiRequired": bool(item["dependencies"].get("aiRequired")),
        },
        "implementations": [
            {
                "id": impl["id"],
                "organization": impl["organization"],
                "independentGroup": impl["independentGroup"],
                "conformancePass": bool(impl["conformancePass"]),
                "openSource": bool(impl["openSource"]),
                "interopPeers": list(impl["interopPeers"]),
            }
            for impl in item["implementations"]
        ],
    }


def technology_evidence_digest(extension: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(technology_evidence_statement(extension))).hexdigest()

DEFAULT_TECHNOLOGY_POLICY: dict[str, Any] = {
    "preserveUnknownCapabilities": True,
    "allowUnregisteredExperimentalNamespaces": True,
    "allowNoAiParticipant": True,
    "requirePublicSpecForCandidate": True,
    "requireConformanceForStandard": True,
    "requireInteropForStandard": True,
    "requireFallbackForStandard": True,
    "requireUnknownPreservationForStandard": True,
    "forbidMandatoryVendorDependency": True,
    "forbidMandatoryCloudDependency": True,
    "forbidMandatoryAiDependency": True,
    "scaleSafeguards": True,
    "emergingStandardGroups": 2,
    "emergingCoreGroups": 3,
    "growingStandardGroups": 3,
    "growingCoreGroups": 4,
    "largeStandardGroups": 4,
    "largeCoreGroups": 5,
    "infrastructureStandardGroups": 5,
    "infrastructureCoreGroups": 7,
    "maxMandatoryCoreExtensions": 24,
}


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _int(value: Any, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def normalize_technology_policy(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    # Preserve policy keys this core does not yet understand. Known keys are
    # normalized below, while future policy metadata round-trips untouched.
    policy = {**DEFAULT_TECHNOLOGY_POLICY, **raw}
    for key in (
        "preserveUnknownCapabilities",
        "allowUnregisteredExperimentalNamespaces",
        "allowNoAiParticipant",
        "requirePublicSpecForCandidate",
        "requireConformanceForStandard",
        "requireInteropForStandard",
        "requireFallbackForStandard",
        "requireUnknownPreservationForStandard",
        "forbidMandatoryVendorDependency",
        "forbidMandatoryCloudDependency",
        "forbidMandatoryAiDependency",
        "scaleSafeguards",
    ):
        if key in raw:
            policy[key] = bool(raw[key])
    for key in (
        "emergingStandardGroups",
        "emergingCoreGroups",
        "growingStandardGroups",
        "growingCoreGroups",
        "largeStandardGroups",
        "largeCoreGroups",
        "infrastructureStandardGroups",
        "infrastructureCoreGroups",
        "maxMandatoryCoreExtensions",
    ):
        if key in raw:
            policy[key] = _int(raw[key], 1, 64, int(policy[key]))
    return policy


def _normalize_implementation(value: dict[str, Any]) -> dict[str, Any]:
    # Start with a copy so implementation-specific evidence survives older cores.
    item = dict(value)
    impl_id = str(value.get("id", "")).strip()[:128]
    group = str(value.get("independentGroup", value.get("organization", impl_id))).strip()[:128]
    item.update({
        "id": impl_id,
        "organization": str(value.get("organization", "")).strip()[:128],
        "independentGroup": group or impl_id,
        "conformancePass": _bool(value.get("conformancePass")),
        "openSource": _bool(value.get("openSource")),
        "interopPeers": sorted({str(peer).strip()[:128] for peer in (value.get("interopPeers") or []) if str(peer).strip()}),
    })
    return item


def normalize_technology_extension(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("technology extension must be an object")
    # Preserve unknown fields by construction. New technology may know more than this core.
    item = dict(value)
    extension_id = str(value.get("id", "")).strip()[:160]
    if not extension_id or "." not in extension_id:
        raise ValueError("technology extension id must be a namespaced identifier")
    maturity = str(value.get("maturity", "experimental")).strip().lower()
    if maturity not in MATURITY:
        raise ValueError(f"technology maturity must be one of {MATURITY}")
    dependency = value.get("dependencies") if isinstance(value.get("dependencies"), dict) else {}
    implementations = []
    seen: set[str] = set()
    for raw_impl in value.get("implementations") or []:
        if not isinstance(raw_impl, dict):
            continue
        impl = _normalize_implementation(raw_impl)
        if not impl["id"] or impl["id"] in seen:
            continue
        seen.add(impl["id"])
        implementations.append(impl)
    item.update({
        "id": extension_id,
        "description": str(value.get("description", "")).strip()[:512],
        "maturity": maturity,
        "requestedCore": _bool(value.get("requestedCore")),
        "mandatoryCore": _bool(value.get("mandatoryCore")),
        "deprecated": _bool(value.get("deprecated")),
        "replacementId": str(value.get("replacementId", "")).strip()[:160],
        "migrationBridge": _bool(value.get("migrationBridge")),
        "adoptionRecordRef": str(value.get("adoptionRecordRef", "")).strip()[:256],
        "publicSpec": _bool(value.get("publicSpec")),
        "conformanceTests": _bool(value.get("conformanceTests")),
        "interoperabilityEvidence": _bool(value.get("interoperabilityEvidence")),
        "fallbackDefined": _bool(value.get("fallbackDefined")),
        "backwardCompatible": _bool(value.get("backwardCompatible"), True),
        "unknownPreservationTested": _bool(value.get("unknownPreservationTested")),
        "productionDeployments": _int(value.get("productionDeployments"), 0, 1_000_000, 0),
        "dependencies": {
            **dependency,
            "mandatoryVendor": str(dependency.get("mandatoryVendor", "")).strip()[:128],
            "cloudRequired": _bool(dependency.get("cloudRequired")),
            "aiRequired": _bool(dependency.get("aiRequired")),
        },
        "implementations": implementations,
    })
    return item


def normalize_technology_extensions(values: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values or []:
        if not isinstance(raw, dict):
            continue
        item = normalize_technology_extension(raw)
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        result.append(item)
    return result


def scale_tier(ecosystem_participants: int) -> str:
    if ecosystem_participants >= 200:
        return "infrastructure"
    if ecosystem_participants >= 50:
        return "large"
    if ecosystem_participants >= 10:
        return "growing"
    return "emerging"


def _thresholds(policy: dict[str, Any], tier: str) -> tuple[int, int]:
    if not policy.get("scaleSafeguards", True):
        return int(policy["emergingStandardGroups"]), int(policy["emergingCoreGroups"])
    return (
        int(policy[f"{tier}StandardGroups"]),
        int(policy[f"{tier}CoreGroups"]),
    )


def evaluate_technology_extension(
    extension: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    ecosystem_participants: int = 0,
) -> dict[str, Any]:
    policy_n = normalize_technology_policy(policy)
    item = normalize_technology_extension(extension)
    tier = scale_tier(ecosystem_participants)
    standard_groups_required, core_groups_required = _thresholds(policy_n, tier)
    implementations = item["implementations"]
    groups = {impl["independentGroup"] or impl["id"] for impl in implementations if impl["id"]}
    conforming_groups = {impl["independentGroup"] or impl["id"] for impl in implementations if impl["id"] and impl["conformancePass"]}
    impl_ids = {impl["id"] for impl in implementations}
    interop_pairs: set[tuple[str, str]] = set()
    impl_by_id = {impl["id"]: impl for impl in implementations}
    for impl in implementations:
        for peer in impl["interopPeers"]:
            if peer not in impl_ids or peer == impl["id"]:
                continue
            peer_impl = impl_by_id[peer]
            if (impl["independentGroup"] or impl["id"]) == (peer_impl["independentGroup"] or peer_impl["id"]):
                continue
            interop_pairs.add(tuple(sorted((impl["id"], peer))))

    dependencies = item["dependencies"]
    vendor_locked = bool(dependencies.get("mandatoryVendor"))
    cloud_locked = bool(dependencies.get("cloudRequired"))
    ai_locked = bool(dependencies.get("aiRequired"))

    blockers: list[str] = []
    candidate_blockers: list[str] = []
    standard_blockers: list[str] = []
    core_blockers: list[str] = []

    community_ready = len(groups) >= 2
    if not community_ready:
        blockers.append("community maturity requires at least two independent implementation groups")

    if policy_n["requirePublicSpecForCandidate"] and not item["publicSpec"]:
        candidate_blockers.append("candidate maturity requires a public specification")
    if len(groups) < 2:
        candidate_blockers.append("candidate maturity requires independent implementations")
    candidate_ready = not candidate_blockers

    # Constitutional standard requirements never rise after adoption. Scale
    # safeguards raise the evidence bar for *new* promotion/revalidation, not
    # compatibility recognition of an already adopted standard.
    baseline_standard_groups = int(policy_n["emergingStandardGroups"])
    base_standard_blockers: list[str] = []
    if len(groups) < baseline_standard_groups:
        base_standard_blockers.append(f"standard maturity requires at least {baseline_standard_groups} independent groups")
    if policy_n["requirePublicSpecForCandidate"] and not item["publicSpec"]:
        base_standard_blockers.append("public specification missing")
    if policy_n["requireConformanceForStandard"] and (not item["conformanceTests"] or len(conforming_groups) < baseline_standard_groups):
        base_standard_blockers.append("public conformance evidence is insufficient")
    if policy_n["requireInteropForStandard"] and (not item["interoperabilityEvidence"] or not interop_pairs):
        base_standard_blockers.append("independent interoperability evidence missing")
    if policy_n["requireFallbackForStandard"] and (not item["fallbackDefined"] or not item["backwardCompatible"]):
        base_standard_blockers.append("fallback/backward-compatibility behavior missing")
    if policy_n["requireUnknownPreservationForStandard"] and not item["unknownPreservationTested"]:
        base_standard_blockers.append("unknown-extension preservation has not been tested")
    if policy_n["forbidMandatoryVendorDependency"] and vendor_locked:
        base_standard_blockers.append("mandatory vendor dependency is incompatible with open standard status")
    if policy_n["forbidMandatoryCloudDependency"] and cloud_locked:
        base_standard_blockers.append("mandatory cloud dependency is incompatible with open standard status")
    if policy_n["forbidMandatoryAiDependency"] and ai_locked:
        base_standard_blockers.append("mandatory AI dependency is incompatible with open standard status")

    standard_blockers = list(base_standard_blockers)
    if len(groups) < standard_groups_required:
        standard_blockers.append(f"current {tier}-scale promotion/revalidation expects {standard_groups_required} independent groups")
    if policy_n["requireConformanceForStandard"] and len(conforming_groups) < standard_groups_required:
        standard_blockers.append("current-scale conformance evidence is not broad enough")
    base_standard_ready = not base_standard_blockers
    standard_ready = not standard_blockers
    grandfathered_standard = bool(item["maturity"] == "standard" and item["adoptionRecordRef"] and base_standard_ready and not standard_ready)
    scale_revalidation_needed = grandfathered_standard

    if not standard_ready:
        core_blockers.extend(standard_blockers)
    if len(groups) < core_groups_required:
        core_blockers.append(f"mandatory core promotion requires {core_groups_required} independent groups at {tier} scale")
    if not item["requestedCore"]:
        core_blockers.append("extension has not requested mandatory-core review")
    core_eligible = not core_blockers

    deprecation_safe = True
    deprecation_blockers: list[str] = []
    if item["deprecated"] and item["maturity"] == "standard":
        if not item["replacementId"]:
            deprecation_blockers.append("deprecated standard must identify a replacement or explicitly remain terminal")
        if item["replacementId"] and not item["migrationBridge"]:
            deprecation_blockers.append("standard replacement lacks a migration/compatibility bridge")
        deprecation_safe = not deprecation_blockers

    highest = "experimental"
    if community_ready:
        highest = "community"
    if candidate_ready:
        highest = "candidate"
    if standard_ready:
        highest = "standard"

    if item["maturity"] == "experimental":
        maturity_valid = True
        maturity_blockers = []
    elif item["maturity"] == "community":
        maturity_valid = community_ready
        maturity_blockers = [] if maturity_valid else blockers
    elif item["maturity"] == "candidate":
        maturity_valid = candidate_ready
        maturity_blockers = [] if maturity_valid else candidate_blockers
    else:
        # A Standard can qualify under current-scale evidence, or remain
        # recognized through an adoption record from an earlier scale. Merely
        # typing maturity=standard is not itself a grandfathering credential.
        maturity_valid = bool(standard_ready or grandfathered_standard)
        if maturity_valid:
            maturity_blockers = []
        elif base_standard_ready and not item["adoptionRecordRef"]:
            maturity_blockers = standard_blockers + ["no adoption record is available for grandfathered Standard recognition"]
        else:
            maturity_blockers = base_standard_blockers

    return {
        "id": item["id"],
        "declaredMaturity": item["maturity"],
        "highestEligibleMaturity": highest,
        "declaredMaturityValid": maturity_valid,
        "maturityBlockers": maturity_blockers,
        "currentScaleStandardReady": standard_ready,
        "scaleRevalidationNeeded": scale_revalidation_needed,
        "grandfatheredStandard": grandfathered_standard,
        "adoptionRecordRef": item["adoptionRecordRef"] or None,
        "scaleRevalidationBlockers": standard_blockers if scale_revalidation_needed else [],
        "coreEligible": core_eligible,
        "coreBlockers": core_blockers,
        "mandatoryCore": bool(item["mandatoryCore"]),
        "deprecated": bool(item["deprecated"]),
        "replacementId": item["replacementId"] or None,
        "deprecationSafe": deprecation_safe,
        "deprecationBlockers": deprecation_blockers,
        "scaleTier": tier,
        "standardIndependentGroupsRequired": standard_groups_required,
        "coreIndependentGroupsRequired": core_groups_required,
        "implementationCount": len(implementations),
        "independentGroupCount": len(groups),
        "conformingIndependentGroupCount": len(conforming_groups),
        "interopPairCount": len(interop_pairs),
        "vendorLocked": vendor_locked,
        "cloudLocked": cloud_locked,
        "aiLocked": ai_locked,
        "unknownFieldsPreserved": True,
    }


def evaluate_technology_registry(
    extensions: list[dict[str, Any]] | None,
    *,
    policy: dict[str, Any] | None = None,
    ecosystem_participants: int = 0,
) -> dict[str, Any]:
    policy_n = normalize_technology_policy(policy)
    extensions_n = normalize_technology_extensions(extensions)
    assessments = [
        evaluate_technology_extension(item, policy=policy_n, ecosystem_participants=ecosystem_participants)
        for item in extensions_n
    ]
    invalid = [item for item in assessments if not item["declaredMaturityValid"]]
    unsafe_core = [item for item in assessments if next(ext for ext in extensions_n if ext["id"] == item["id"])["requestedCore"] and not item["coreEligible"]]
    scale_revalidation = [item for item in assessments if item.get("scaleRevalidationNeeded")]
    unsafe_deprecations = [item for item in assessments if not item.get("deprecationSafe", True)]
    mandatory_core = [item for item in assessments if item.get("mandatoryCore")]
    core_budget_exceeded = len(mandatory_core) > int(policy_n["maxMandatoryCoreExtensions"])
    locked_standards = [
        item for item in assessments
        if item["declaredMaturity"] == "standard" and (item["vendorLocked"] or item["cloudLocked"] or item["aiLocked"])
    ]
    policy_failures: list[str] = []
    if not policy_n["preserveUnknownCapabilities"]:
        policy_failures.append("unknown capabilities are not guaranteed to survive")
    if not policy_n["allowUnregisteredExperimentalNamespaces"]:
        policy_failures.append("experimental technology requires central registration")
    if not policy_n["allowNoAiParticipant"]:
        policy_failures.append("no-AI participants are not protected")
    if locked_standards:
        policy_failures.append("declared standards contain mandatory vendor/cloud/AI dependencies")
    if unsafe_deprecations:
        policy_failures.append("standard deprecation lacks a migration-safe path")
    if core_budget_exceeded:
        policy_failures.append("mandatory core extension budget is exceeded; new capabilities should remain profiles/extensions")

    openness = "open"
    if policy_failures or invalid:
        openness = "guarded"
    if unsafe_core or len(policy_failures) >= 2:
        openness = "at-risk"

    tier = scale_tier(ecosystem_participants)
    standard_required, core_required = _thresholds(policy_n, tier)
    return {
        "openness": openness,
        "scaleTier": tier,
        "ecosystemParticipants": max(0, int(ecosystem_participants)),
        "policy": policy_n,
        "extensionCount": len(extensions_n),
        "experimentalCount": sum(1 for ext in extensions_n if ext["maturity"] == "experimental"),
        "standardCount": sum(1 for ext in extensions_n if ext["maturity"] == "standard"),
        "requestedCoreCount": sum(1 for ext in extensions_n if ext["requestedCore"]),
        "mandatoryCoreCount": len(mandatory_core),
        "maxMandatoryCoreExtensions": int(policy_n["maxMandatoryCoreExtensions"]),
        "coreBudgetExceeded": core_budget_exceeded,
        "standardIndependentGroupsRequired": standard_required,
        "coreIndependentGroupsRequired": core_required,
        "preserveUnknownCapabilities": bool(policy_n["preserveUnknownCapabilities"]),
        "experimentalWithoutPermission": bool(policy_n["allowUnregisteredExperimentalNamespaces"]),
        "noAiParticipantValid": bool(policy_n["allowNoAiParticipant"]),
        "invalidDeclaredMaturityIds": [item["id"] for item in invalid],
        "unsafeCoreRequestIds": [item["id"] for item in unsafe_core],
        "scaleRevalidationIds": [item["id"] for item in scale_revalidation],
        "unsafeDeprecationIds": [item["id"] for item in unsafe_deprecations],
        "policyFailures": policy_failures,
        "extensions": assessments,
    }


def negotiate_technology_capabilities(local: list[str] | None, remote: list[str] | None) -> dict[str, Any]:
    """Exact capability negotiation with lossless unknown preservation.

    Adapters may provide explicit translators above this layer. The core never
    guesses that two differently named capabilities are equivalent merely
    because they sound similar.
    """
    local_set = {str(item).strip()[:192] for item in (local or []) if str(item).strip()}
    remote_set = {str(item).strip()[:192] for item in (remote or []) if str(item).strip()}
    common = sorted(local_set & remote_set)
    local_only = sorted(local_set - remote_set)
    remote_only = sorted(remote_set - local_set)
    return {
        "common": common,
        "localOnly": local_only,
        "remoteOnly": remote_only,
        "preservedUnknown": sorted(local_set | remote_set),
        "executeCommonOnly": True,
        "implicitCoercion": False,
        "translationRequired": bool(local_only or remote_only),
    }
