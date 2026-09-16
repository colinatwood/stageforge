"""Conservative OS class-driver assessment and reviewed exact package matching."""
from __future__ import annotations
from datetime import date
import json
import re
from pathlib import Path
from urllib.parse import urlparse

_HARDWARE_ID = re.compile(r"USB:[0-9A-F]{4}:[0-9A-F]{4}")
_REVIEW_CONFIDENCE = {"low", "moderate", "high"}
_EVIDENCE_KINDS = {"vendor-download", "hardware-id-source", "vendor-support"}


def _https_url(value: object) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme == "https" and bool(parsed.hostname)


def _iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _valid_package(item):
    if not isinstance(item, dict): return False
    if not _HARDWARE_ID.fullmatch(str(item.get("hardwareId", ""))): return False
    if item.get("os") not in ("Linux", "Windows", "Darwin") or not item.get("architecture"): return False
    if not isinstance(item.get("osReleases"), list) or not all(isinstance(v, str) and v for v in item["osReleases"]): return False
    return _https_url(item.get("url")) and isinstance(item.get("publisher"), str) and bool(item["publisher"])


def _review_state(item: dict, as_of: date) -> str:
    reviewed = _iso_date(item.get("reviewedAt")); expires = _iso_date(item.get("reviewExpiresAt")); released = _iso_date(item.get("releaseDate"))
    evidence = item.get("evidence")
    if not (reviewed and expires and released and reviewed <= expires and released <= reviewed): return "unreviewed"
    if item.get("reviewConfidence") not in _REVIEW_CONFIDENCE or item.get("catalogClaim") != "package-metadata-only": return "unreviewed"
    if not isinstance(item.get("product"), str) or not item["product"].strip(): return "unreviewed"
    if not isinstance(evidence, list) or len(evidence) < 2: return "unreviewed"
    for source in evidence:
        if not isinstance(source, dict) or source.get("kind") not in _EVIDENCE_KINDS or not _https_url(source.get("url")): return "unreviewed"
    if reviewed > as_of: return "review-date-in-future"
    return "stale" if as_of > expires else "current"


def load_catalog(path):
    try: raw = json.loads(Path(path).read_text())
    except (OSError, ValueError, TypeError): return []
    if not isinstance(raw, dict): return []
    # v1 remains readable for locally curated compatibility, but only v2 review
    # evidence can produce a current reviewed match.
    if raw.get("schemaVersion") not in (1, 2): return []
    return [dict(item) for item in raw.get("packages", []) if _valid_package(item)]


def _public_package(item: dict, review_state: str) -> dict:
    keys = ("publisher", "product", "package", "version", "url", "releaseDate", "reviewedAt", "reviewExpiresAt", "reviewConfidence", "catalogClaim")
    result = {key:item[key] for key in keys if key in item}
    result["reviewState"] = review_state
    result["evidence"] = [{"kind":source.get("kind"), "url":source.get("url")} for source in item.get("evidence", []) if isinstance(source, dict)]
    return result


def assess_driver(device, system, release, architecture, catalog=(), *, as_of: date | None = None):
    today = as_of or date.today()
    hardware_id = device.get("hardwareId")
    candidates = [item for item in catalog if item["hardwareId"] == hardware_id and item["os"] == system and
                  item["architecture"] == architecture and release in item["osReleases"]]
    reviewed = [(item, _review_state(item, today)) for item in candidates]
    exact = [_public_package(item, state) for item, state in reviewed]
    current = [item for item, state in reviewed if state == "current"]
    stale = any(state == "stale" for _, state in reviewed)
    review_required = bool(candidates) and not current
    driver = str(device.get("driver") or "")
    classes = set(device.get("interfaceClasses") or [])
    problem = device.get("osProblem")
    if problem not in (None, 0): status = "os-problem"
    elif system == "Linux" and "01" in classes and "snd-usb-audio" in driver: status = "class-driver-bound"
    elif system == "Linux" and "01" in classes: status = "audio-class-detected-driver-unverified"
    elif system == "Windows" and driver.lower() in ("usbaudio", "usbaudio2"): status = "class-driver-bound"
    elif current: status = "curated-exact-match"
    elif stale: status = "curated-match-review-stale"
    elif candidates: status = "curated-match-unreviewed"
    else: status = "no-verified-match"
    return {"status":status, "classDriverEvidence": status == "class-driver-bound",
            "exactPackages":exact, "catalogReviewRequired":review_required,
            "catalogReviewStale":stale, "searchLinksAreVerifiedMatches":False,
            "automaticInstallAllowed":False, "qualification":"hardware-tests-required"}


def audit_catalog(path, *, as_of: date | None = None, warn_days: int = 30):
    today=as_of or date.today();warn=max(0,min(int(warn_days),3650))
    try:raw=json.loads(Path(path).read_text())
    except (OSError,ValueError,TypeError) as exc:
        return {"documentType":"org.upp.driver-catalog-audit-report","schemaVersion":1,"asOf":today.isoformat(),"warnDays":warn,"catalogReadable":False,"catalogUsable":False,"reviewAttentionRequired":True,"counts":{"total":0,"current":0,"reviewDue":0,"stale":0,"unreviewed":0,"invalid":0},"entries":[],"error":str(exc)[:512]}
    packages=raw.get("packages",[]) if isinstance(raw,dict) else []
    if not isinstance(packages,list):packages=[]
    entries=[];counts={"total":len(packages),"current":0,"reviewDue":0,"stale":0,"unreviewed":0,"invalid":0}
    for index,item in enumerate(packages):
        base={"index":index}
        if isinstance(item,dict):
            for key in ("hardwareId","product","os","architecture","publisher","version","reviewedAt","reviewExpiresAt"):
                if key in item:base[key]=item[key]
        if not _valid_package(item):
            base.update({"reviewState":"invalid","reviewDue":True,"daysUntilExpiry":None});counts["invalid"]+=1;entries.append(base);continue
        state=_review_state(item,today);expires=_iso_date(item.get("reviewExpiresAt"));days=(expires-today).days if expires else None
        due=state!="current" or (days is not None and days<=warn)
        if state=="current":counts["current"]+=1
        elif state=="stale":counts["stale"]+=1
        else:counts["unreviewed"]+=1
        if due:counts["reviewDue"]+=1
        base.update({"reviewState":state,"reviewDue":due,"daysUntilExpiry":days});entries.append(base)
    usable=bool(isinstance(raw,dict) and raw.get("schemaVersion") in (1,2) and counts["invalid"]==0 and counts["stale"]==0 and counts["unreviewed"]==0)
    return {"documentType":"org.upp.driver-catalog-audit-report","schemaVersion":1,"asOf":today.isoformat(),"warnDays":warn,"catalogReadable":True,"catalogUsable":usable,"reviewAttentionRequired":counts["reviewDue"]>0,"counts":counts,"entries":entries}
