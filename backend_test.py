"""
FINAL DEEP REGRESSION GATE — T11 OBSERVABILITY CONTRACT FREEZE
Pre-T10.2C execution sprint.

8 ZONES — fail any zone → block T10.2C until fixed.
DO NOT MUTATE BACKEND CODE.
"""
from __future__ import annotations

import os
import json
import time
import subprocess
import uuid
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env", override=False)

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://merge-verify-4.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
ADMIN_SECRET = "dev-access-secret-change-me-32chars-long-xx"

_mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _mongo[os.environ.get("DB_NAME", "test_database")]

COLLECTIONS_11 = [
    "paper_outcomes", "paper_orders_v2", "paper_positions_v2", "paper_events_v2",
    "gate_decisions", "operator_access", "billing_invoices",
    "billing_reconciliation_findings", "billing_audit_v1",
    "paper_accounts_v2", "trading_outcomes_v2",
]

EXPECTED_PIPELINE_VERSION = "t6+t8+t9+t10+tier4c1"


def login_admin() -> str:
    r = requests.post(f"{API}/admin/auth/login", json={"secret": ADMIN_SECRET}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def snapshot_counts() -> dict:
    return {c: _db[c].count_documents({}) for c in COLLECTIONS_11}


def diff_counts(before: dict, after: dict) -> list:
    return [(c, before[c], after[c], after[c] - before[c]) for c in COLLECTIONS_11 if before[c] != after[c]]


def aget(path: str, headers: dict, **params) -> requests.Response:
    return requests.get(f"{API}{path}", headers=headers, params=params, timeout=30)


def apost(path: str, headers: dict, body=None) -> requests.Response:
    return requests.post(f"{API}{path}", headers=headers, json=(body or {}), timeout=60)


# ZONE 1 ─────────────────────────────────────────────────────────────
def zone1_pytest() -> dict:
    suites = [
        "tests/test_sprint_tier1_product_model.py",
        "tests/test_sprint_tier2_security_enforcement.py",
        "tests/test_sprint_tier3_governance.py",
        "tests/test_sprint_tier3c_governance_mutations.py",
        "tests/test_sprint_tier4a_billing_bridge.py",
        "tests/test_sprint_tier4b2_reconciliation.py",
        "tests/test_sprint_tier4b3_analytics.py",
        "tests/test_sprint_tier4c1_paywall.py",
        "tests/test_sprint_t4_calibration.py",
        "tests/test_sprint_t6_windowed_calibration.py",
        "tests/test_sprint_t8_adaptive_risk.py",
        "tests/test_sprint_t9_portfolio_gate.py",
        "tests/test_sprint_t10_1_broker_bridge.py",
        "tests/test_sprint_t10_2b_binance_readonly.py",
        "tests/test_sprint_t11_1_attribution.py",
        "tests/test_sprint_t11_1c_outcome_writer.py",
        "tests/test_sprint_t11_2b_drilldowns.py",
    ]
    cmd = ["python", "-m", "pytest", *suites, "-q", "--tb=short", "--no-header"]
    started = time.time()
    proc = subprocess.run(cmd, cwd="/app/backend", capture_output=True, text=True, timeout=600)
    dur = time.time() - started
    out = proc.stdout + "\n" + proc.stderr
    tail = "\n".join(out.strip().splitlines()[-30:])
    import re
    summary_line = ""
    for line in reversed(out.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            summary_line = line.strip()
            break
    p = re.search(r"(\d+)\s+passed", summary_line)
    f = re.search(r"(\d+)\s+failed", summary_line)
    s = re.search(r"(\d+)\s+skipped", summary_line)
    e = re.search(r"(\d+)\s+error", summary_line)
    return {
        "passed": int(p.group(1)) if p else 0,
        "failed": int(f.group(1)) if f else 0,
        "skipped": int(s.group(1)) if s else 0,
        "errors": int(e.group(1)) if e else 0,
        "rc": proc.returncode,
        "dur": round(dur, 1),
        "summary_line": summary_line,
        "tail": tail,
    }


# ZONE 2 ─────────────────────────────────────────────────────────────
def zone2_readonly(token: str) -> dict:
    H = {"Authorization": f"Bearer {token}"}
    before = snapshot_counts()
    statuses = {}
    windows = ("7d", "30d", "90d", "all")

    for w in windows:
        for ep in (
            "/admin/attribution/summary",
            "/admin/attribution/lost-opportunity",
            "/admin/attribution/per-asset",
            "/admin/attribution/assets",
            "/admin/attribution/gate-rule-breakdown",
            "/admin/attribution/confidence-distribution",
            "/admin/attribution/exposure-histograms",
        ):
            params = {"window": w}
            if ep == "/admin/attribution/per-asset":
                params["symbol"] = "BTC"
            r = aget(ep, H, **params)
            statuses[f"GET {ep}?window={w}"] = r.status_code

    r = aget("/admin/attribution/pipeline-version", H)
    statuses["GET /admin/attribution/pipeline-version"] = r.status_code

    for w in ("7d", "30d", "90d"):
        r = aget("/admin/billing/analytics/summary", H, window=w)
        statuses[f"GET /admin/billing/analytics/summary?window={w}"] = r.status_code

    r = apost("/admin/billing/reconciliation/scan", H, {})
    statuses["POST /admin/billing/reconciliation/scan"] = r.status_code

    r = aget("/admin/billing/reconciliation/findings", H, limit=50)
    statuses["GET /admin/billing/reconciliation/findings?limit=50"] = r.status_code

    after = snapshot_counts()
    deltas = diff_counts(before, after)
    return {
        "statuses": statuses,
        "before": before,
        "after": after,
        "deltas": deltas,
        "all_2xx": all(c in (200, 201) for c in statuses.values()),
    }


# ZONE 3 ─────────────────────────────────────────────────────────────
def _cap_value(oa_doc, name):
    if not oa_doc:
        return None
    oa = oa_doc.get("operatorAccess") or {}
    if name == "liveAuthority.granted":
        return ((oa.get("liveAuthority") or {}).get("granted"))
    if name == "consoleAccess":
        return oa.get("consoleAccess")
    if name == "capabilityOverrides":
        return oa.get("capabilityOverrides")
    return None


def zone3_governance(token: str) -> dict:
    H = {"Authorization": f"Bearer {token}"}
    out = {"sub": {}}

    # 3.1 TRADER ⇏ governance
    uid_a = f"regress_t10_2c_pre_a_{uuid.uuid4().hex[:8]}"
    r = apost("/billing/invoices", H, {"userId": uid_a, "productCode": "TRADER"})
    inv_id_a = (r.json().get("invoice") or {}).get("invoiceId") if r.status_code == 200 else None
    r2 = apost("/billing/invoices/confirm", H, {"invoiceId": inv_id_a}) if inv_id_a else None

    oa_a = _db.operator_access.find_one({"userId": uid_a.lower()}, {"_id": 0})
    tier_a = (oa_a or {}).get("tier")
    live_a = _cap_value(oa_a, "liveAuthority.granted")
    console_a = _cap_value(oa_a, "consoleAccess")
    overrides_a = _cap_value(oa_a, "capabilityOverrides")

    cap_r = requests.get(f"{API}/me/capabilities", headers={"X-User-Id": uid_a}, timeout=15)
    cap_a = cap_r.json() if cap_r.status_code == 200 else {}
    paper_a_node = (((cap_a or {}).get("capabilities") or {}).get("paperTrading"))
    paper_a_eff = paper_a_node.get("effective") if isinstance(paper_a_node, dict) else paper_a_node

    refund_r = apost("/billing/invoices/refund", H, {"invoiceId": inv_id_a, "reason": "regression_t10_2c_pre"}) if inv_id_a else None
    oa_a_aft = _db.operator_access.find_one({"userId": uid_a.lower()}, {"_id": 0})
    tier_a_aft = (oa_a_aft or {}).get("tier")

    out["sub"]["3.1_TRADER_no_governance"] = {
        "userId": uid_a,
        "create_status": r.status_code,
        "confirm_status": r2.status_code if r2 else None,
        "tier_after_confirm": tier_a,
        "liveAuthority.granted": live_a,
        "consoleAccess": console_a,
        "capabilityOverrides": overrides_a,
        "paperTrading_effective": paper_a_eff,
        "refund_status": refund_r.status_code if refund_r else None,
        "tier_after_refund": tier_a_aft,
        "PASS": (
            tier_a == "trader"
            and paper_a_eff is True
            and not live_a
            and not console_a
            and (not overrides_a or overrides_a == {})
            and tier_a_aft == "free"
        ),
    }

    # 3.2 PRO ⇏ trader caps
    uid_b = f"regress_t10_2c_pre_b_{uuid.uuid4().hex[:8]}"
    r = apost("/billing/invoices", H, {"userId": uid_b, "productCode": "PRO"})
    inv_id_b = (r.json().get("invoice") or {}).get("invoiceId") if r.status_code == 200 else None
    r2 = apost("/billing/invoices/confirm", H, {"invoiceId": inv_id_b}) if inv_id_b else None
    oa_b = _db.operator_access.find_one({"userId": uid_b.lower()}, {"_id": 0})
    tier_b = (oa_b or {}).get("tier")
    live_b = _cap_value(oa_b, "liveAuthority.granted")
    console_b = _cap_value(oa_b, "consoleAccess")
    cap_r = requests.get(f"{API}/me/capabilities", headers={"X-User-Id": uid_b}, timeout=15)
    cap_b = cap_r.json() if cap_r.status_code == 200 else {}
    paper_b_node = (((cap_b or {}).get("capabilities") or {}).get("paperTrading"))
    paper_b_eff = paper_b_node.get("effective") if isinstance(paper_b_node, dict) else paper_b_node

    out["sub"]["3.2_PRO_no_trader_caps"] = {
        "userId": uid_b,
        "confirm_status": r2.status_code if r2 else None,
        "tier": tier_b,
        "paperTrading_effective": paper_b_eff,
        "liveAuthority.granted": live_b,
        "consoleAccess": console_b,
        "PASS": (tier_b == "pro" and paper_b_eff in (False, None) and not live_b and not console_b),
    }

    # 3.3 grant-live-authority typed-conf + pipelineVersion
    uid_c = f"regress_t10_2c_pre_c_{uuid.uuid4().hex[:8]}"
    r = apost("/billing/invoices", H, {"userId": uid_c, "productCode": "PRO"})
    inv_id_c = (r.json().get("invoice") or {}).get("invoiceId") if r.status_code == 200 else None
    apost("/billing/invoices/confirm", H, {"invoiceId": inv_id_c})
    r_grant_paper = apost("/admin/operator-access/grant", H, {"userId": uid_c, "mode": "paper"})

    r_wrong = apost("/admin/operator-access/grant-live-authority", H, {
        "userId": uid_c, "typedConfirmation": "WRONG", "reason": "regression test",
    })
    r_right = apost("/admin/operator-access/grant-live-authority", H, {
        "userId": uid_c, "typedConfirmation": "GRANT LIVE TRADING", "reason": "regression test",
    })

    gd_doc = _db.gate_decisions.find_one(sort=[("ts", -1)],
                                          projection={"_id": 0, "pipelineVersion": 1, "decisionId": 1, "ts": 1})

    out["sub"]["3.3_grant_live_auth_typed_conf"] = {
        "userId": uid_c,
        "grant_paper_status": r_grant_paper.status_code,
        "wrong_status": r_wrong.status_code,
        "wrong_body": r_wrong.json() if r_wrong.status_code != 200 else None,
        "right_status": r_right.status_code,
        "right_body": r_right.json() if r_right.status_code != 200 else "OK",
        "gate_decisions_latest_pipelineVersion": (gd_doc or {}).get("pipelineVersion"),
        "PASS": (
            r_wrong.status_code in (400, 422)
            and r_right.status_code == 200
            and (gd_doc or {}).get("pipelineVersion") == EXPECTED_PIPELINE_VERSION
        ),
    }
    out["pass_all"] = all(s["PASS"] for s in out["sub"].values())
    return out


# ZONE 4 ─────────────────────────────────────────────────────────────
def zone4_pipelineversion(token: str) -> dict:
    H = {"Authorization": f"Bearer {token}"}
    v = {}

    for w in ("7d", "30d", "90d", "all"):
        r = aget("/admin/attribution/summary", H, window=w)
        v[f"summary?window={w}"] = (r.json() or {}).get("pipelineVersion") if r.status_code == 200 else f"HTTP {r.status_code}"

    r = aget("/admin/attribution/lost-opportunity", H, window="30d")
    v["lost-opportunity?window=30d"] = (r.json() or {}).get("pipelineVersion") if r.status_code == 200 else f"HTTP {r.status_code}"

    r = aget("/admin/attribution/per-asset", H, window="30d", symbol="BTC")
    v["per-asset?window=30d&symbol=BTC"] = (r.json() or {}).get("pipelineVersion") if r.status_code == 200 else f"HTTP {r.status_code}"

    r = aget("/admin/attribution/pipeline-version", H)
    v["pipeline-version"] = (r.json() or {}).get("pipelineVersion") if r.status_code == 200 else f"HTTP {r.status_code}"

    r = aget("/admin/attribution/assets", H, window="30d")
    v["assets?window=30d"] = (r.json() or {}).get("pipelineVersion") if r.status_code == 200 else f"HTTP {r.status_code}"

    r = aget("/admin/attribution/gate-rule-breakdown", H, window="30d")
    v["gate-rule-breakdown?window=30d"] = (r.json() or {}).get("pipelineVersion") if r.status_code == 200 else f"HTTP {r.status_code}"

    r = aget("/admin/attribution/confidence-distribution", H, window="30d")
    v["confidence-distribution?window=30d"] = (r.json() or {}).get("pipelineVersion") if r.status_code == 200 else f"HTTP {r.status_code}"

    r = aget("/admin/attribution/exposure-histograms", H, window="30d")
    v["exposure-histograms?window=30d"] = (r.json() or {}).get("pipelineVersion") if r.status_code == 200 else f"HTTP {r.status_code}"

    # Mongo samples
    for coll, idkey, query in [
        ("gate_decisions", "decisionId", {"pipelineVersion": {"$exists": True}}),
        ("paper_orders_v2", "orderId", {"lineageId": {"$ne": None}, "pipelineVersion": {"$exists": True}}),
        ("paper_positions_v2", "positionId", {"lineageId": {"$ne": None}, "pipelineVersion": {"$exists": True}}),
        ("paper_outcomes", "outcomeId", {"pipelineVersion": {"$exists": True}}),
        ("paper_events_v2", "eventId", {"type": "POSITION_OPENED", "pipelineVersion": {"$exists": True}}),
    ]:
        rows = list(_db[coll].find(query, {"_id": 0, idkey: 1, "pipelineVersion": 1}).limit(3))
        for i, doc in enumerate(rows):
            v[f"{coll}[{i}]={doc.get(idkey,'?')}"] = doc.get("pipelineVersion")
        if not rows:
            v[f"{coll}.samples"] = "NONE_FOUND"

    deviations = {k: val for k, val in v.items() if val != EXPECTED_PIPELINE_VERSION and val != "NONE_FOUND"}
    return {
        "expected": EXPECTED_PIPELINE_VERSION,
        "versions": v,
        "deviations": deviations,
        "PASS": len(deviations) == 0,
    }


# ZONE 5 ─────────────────────────────────────────────────────────────
def zone5_no_mutation(token: str) -> dict:
    H = {"Authorization": f"Bearer {token}"}
    results = {}
    paths = [
        "/admin/attribution/summary",
        "/admin/attribution/lost-opportunity",
        "/admin/attribution/pipeline-version",
        "/admin/attribution/per-asset",
        "/admin/attribution/assets",
        "/admin/attribution/gate-rule-breakdown",
        "/admin/attribution/confidence-distribution",
        "/admin/attribution/exposure-histograms",
        "/admin/attribution/gate-decisions",
    ]
    violations = []
    for p in paths:
        for method in ("POST", "PATCH", "PUT", "DELETE"):
            r = requests.request(method, f"{API}{p}", headers=H, json={}, timeout=15)
            results[f"{method} {p}"] = r.status_code
            if r.status_code not in (404, 405):
                violations.append((method, p, r.status_code, r.text[:200]))

    grep_gd = subprocess.run(
        ["grep", "-rEn", r"gate_decisions\.(delete|update|replace)", "/app/backend/routes/"],
        capture_output=True, text=True,
    )
    grep_po = subprocess.run(
        ["grep", "-rEn", r"paper_outcomes\.(delete|update|replace)", "/app/backend/routes/"],
        capture_output=True, text=True,
    )

    return {
        "results": results,
        "violations": violations,
        "grep_gate_decisions_mutations": grep_gd.stdout.strip().splitlines(),
        "grep_paper_outcomes_mutations": grep_po.stdout.strip().splitlines(),
        "PASS": len(violations) == 0,
    }


# ZONE 6 ─────────────────────────────────────────────────────────────
def zone6_sparse(token: str) -> dict:
    H = {"Authorization": f"Bearer {token}"}
    out = {}

    pre_t11 = _db.paper_outcomes.find_one({"lineageId": None})
    out["6.1_paper_outcomes_lineage_null"] = {
        "found": pre_t11 is not None,
        "sample_id": (pre_t11 or {}).get("outcomeId") if pre_t11 else None,
        "PASS": pre_t11 is None,
    }

    legacy_closed = _db.paper_positions_v2.find_one({"status": "CLOSED", "lineageId": {"$in": [None]}})
    legacy_count = _db.paper_positions_v2.count_documents({"status": "CLOSED", "lineageId": {"$in": [None]}})
    legacy_count2 = _db.paper_positions_v2.count_documents({"status": "CLOSED", "lineageId": {"$exists": False}})
    r_all = aget("/admin/attribution/summary", H, window="all")
    summary_all = r_all.json() if r_all.status_code == 200 else {}
    raw_samples = ((summary_all.get("dataAvailability") or {}).get("rawSamples")) if isinstance(summary_all, dict) else None
    out["6.2_legacy_closed_positions"] = {
        "legacy_with_null_lineageId": legacy_count,
        "legacy_without_lineageId_field": legacy_count2,
        "legacy_sample_id": (legacy_closed or {}).get("positionId"),
        "summary_all_status": r_all.status_code,
        "rawSamples": raw_samples,
        "PASS": r_all.status_code == 200,
    }

    r_cd = aget("/admin/attribution/confidence-distribution", H, window="7d")
    cd_json = r_cd.json() if r_cd.status_code == 200 else None
    buckets = (cd_json or {}).get("buckets") or []
    bucket_names = sorted([b.get("bucket") for b in buckets])
    out["6.3_confidence_distribution_sparse"] = {
        "status": r_cd.status_code,
        "totalOutcomes": (cd_json or {}).get("totalOutcomes"),
        "buckets_count": len(buckets),
        "bucket_names": bucket_names,
        "PASS": (r_cd.status_code == 200 and len(buckets) == 4 and set(bucket_names) == {"high", "low", "mid", "unknown"}),
    }

    r_eh = aget("/admin/attribution/exposure-histograms", H, window="7d")
    eh_json = r_eh.json() if r_eh.status_code == 200 else None
    bands = (eh_json or {}).get("bands") or []
    out["6.4_exposure_histograms_sparse"] = {
        "status": r_eh.status_code,
        "bands_count": len(bands),
        "band_names": [b.get("band") for b in bands],
        "PASS": (r_eh.status_code == 200 and len(bands) == 6),
    }

    r_pa = aget("/admin/attribution/per-asset", H, window="30d", symbol="NEVEREXISTED")
    pa_json = r_pa.json() if r_pa.status_code == 200 else None
    # API uses `gated` (not `outcomes`) as the realized-outcomes sub-block
    outcomes_tc = ((pa_json or {}).get("gated") or {}).get("tradeCount")
    gate_bc = ((pa_json or {}).get("gateBlocks") or {}).get("blockedCount")
    out["6.5_per_asset_neverexisted"] = {
        "status": r_pa.status_code,
        "tradeCount": outcomes_tc,
        "blockedCount": gate_bc,
        "PASS": r_pa.status_code == 200 and outcomes_tc == 0 and gate_bc == 0,
    }

    out["pass_all"] = all(v.get("PASS") for v in out.values() if isinstance(v, dict))
    return out


# ZONE 7 ─────────────────────────────────────────────────────────────
def zone7_recon_no_attribution(token: str) -> dict:
    H = {"Authorization": f"Bearer {token}"}
    KEYS = ["gate_decisions", "paper_outcomes", "paper_positions_v2"]
    before = {k: _db[k].count_documents({}) for k in KEYS}
    r_scan = apost("/admin/billing/reconciliation/scan", H, {})
    r_an = aget("/admin/billing/analytics/summary", H, window="30d")
    after = {k: _db[k].count_documents({}) for k in KEYS}
    deltas = {k: after[k] - before[k] for k in KEYS}
    return {
        "scan_status": r_scan.status_code,
        "analytics_status": r_an.status_code,
        "before": before, "after": after, "deltas": deltas,
        "PASS": all(v == 0 for v in deltas.values()),
    }


# ZONE 8 ─────────────────────────────────────────────────────────────
def zone8_paywall_no_attribution(token: str) -> dict:
    KEYS = ["gate_decisions", "paper_outcomes"]
    before = {k: _db[k].count_documents({}) for k in KEYS}
    paywall_uid = f"regress_t10_2c_pre_paywall_{uuid.uuid4().hex[:8]}"
    r = requests.post(
        f"{API}/me/billing/invoices",
        headers={"X-User-Id": paywall_uid, "Content-Type": "application/json"},
        json={"productCode": "PRO"},
        timeout=30,
    )
    after = {k: _db[k].count_documents({}) for k in KEYS}
    deltas = {k: after[k] - before[k] for k in KEYS}
    return {
        "paywall_status": r.status_code,
        "invoice_id": (r.json().get("invoice") or {}).get("invoiceId") if r.status_code == 200 else None,
        "before": before, "after": after, "deltas": deltas,
        "PASS": all(v == 0 for v in deltas.values()),
    }


def main():
    print(f"# Final Deep Regression Gate · base={BASE}")
    token = login_admin()
    print(f"# admin token len={len(token)}")
    results = {}

    print("\n## ZONE 1 — PYTEST REGRESSION (sequential 17 suites)")
    z1 = zone1_pytest()
    results["zone1"] = z1
    print(json.dumps({k: v for k, v in z1.items() if k != "tail"}, indent=2))
    print("--- pytest tail ---")
    print(z1["tail"])

    print("\n## ZONE 2 — READ-ONLY ATTRIBUTION INVARIANT")
    z2 = zone2_readonly(token)
    results["zone2"] = z2
    print(json.dumps({"statuses": z2["statuses"], "deltas": z2["deltas"], "all_2xx": z2["all_2xx"]}, indent=2))
    print("before/after counts:")
    for k in COLLECTIONS_11:
        print(f"  {k}: {z2['before'][k]} -> {z2['after'][k]}  delta={z2['after'][k]-z2['before'][k]}")

    print("\n## ZONE 3 — GOVERNANCE BOUNDARY")
    z3 = zone3_governance(token)
    results["zone3"] = z3
    print(json.dumps(z3, indent=2, default=str))

    print("\n## ZONE 4 — PIPELINEVERSION COHERENCE")
    z4 = zone4_pipelineversion(token)
    results["zone4"] = z4
    print(json.dumps(z4, indent=2))

    print("\n## ZONE 5 — NO HIDDEN MUTATION CHANNELS")
    z5 = zone5_no_mutation(token)
    results["zone5"] = z5
    print(json.dumps(z5, indent=2))

    print("\n## ZONE 6 — SPARSE LINEAGE STABILITY")
    z6 = zone6_sparse(token)
    results["zone6"] = z6
    print(json.dumps(z6, indent=2, default=str))

    print("\n## ZONE 7 — RECONCILIATION + ANALYTICS DO NOT TOUCH ATTRIBUTION")
    z7 = zone7_recon_no_attribution(token)
    results["zone7"] = z7
    print(json.dumps(z7, indent=2))

    print("\n## ZONE 8 — PAYWALL DOES NOT TOUCH ATTRIBUTION")
    z8 = zone8_paywall_no_attribution(token)
    results["zone8"] = z8
    print(json.dumps(z8, indent=2))

    print("\n# ═══ FINAL VERDICT ═══")
    zone_pass = {
        "ZONE 1 pytest": z1["failed"] == 0 and z1["errors"] == 0,
        "ZONE 2 readonly": (len(z2["deltas"]) == 0) and z2["all_2xx"],
        "ZONE 3 governance": z3.get("pass_all", False),
        "ZONE 4 pipelineVersion": z4.get("PASS", False),
        "ZONE 5 no mutation": z5.get("PASS", False),
        "ZONE 6 sparse": z6.get("pass_all", False),
        "ZONE 7 recon": z7.get("PASS", False),
        "ZONE 8 paywall": z8.get("PASS", False),
    }
    for k, val in zone_pass.items():
        print(f"  {'PASS' if val else 'FAIL'} {k}")
    overall = all(zone_pass.values())
    print(f"\n  → OVERALL: {'GREEN — T11 CONTRACT FROZEN' if overall else 'RED — T10.2C BLOCKED'}")
    with open("/app/backend_test_result.json", "w") as f:
        json.dump(results, f, indent=2, default=str)


if __name__ == "__main__":
    main()
