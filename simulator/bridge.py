"""Submit only bidder-visible evidence and GC inputs through the POC HTTP API."""

import hashlib
import json
import os

import requests
from core import read, save, write_document

API = os.getenv("WYRE_API_URL", "http://127.0.0.1:8000").rstrip("/") + "/api"


def call(method, path, **kwargs):
    r = requests.request(method, API + path, timeout=(5, 240), **kwargs)
    if not r.ok:
        raise ValueError(f"POC {r.status_code}: {r.text[:400]}")
    return r.json()


def submit(folder, run, policy, models):
    signature = hashlib.sha256(
        json.dumps([policy, models], sort_keys=True).encode()
    ).hexdigest()[:16]
    path = folder / f"poc-{signature}.json"
    state = (
        read(path)
        if path.exists()
        else {"documents": {}, "models": models, "policy": policy}
    )
    if "project" not in state:
        state["project"] = call(
            "POST", "/projects", json={"name": "Simulator · " + run["scenario"]["name"]}
        )["id"]
        save(path, state)
    if "package" not in state:
        state["package"] = call(
            "POST",
            f"/projects/{state['project']}/packages",
            json={"name": run["scenario"]["trade"]},
        )["id"]
        save(path, state)
    base = "/packages/" + state["package"]
    call(
        "PUT",
        base + "/settings",
        json={"stage_models": models, "ai_text": False, "ai_auto": False},
    )
    policy_file = "policy-" + signature + ".docx"
    if not (folder / policy_file).exists():
        clauses = [
            [policy["label"], policy["template"]],
            ["Exclude unrelated bids, declines, budget quotes, and withdrawals."],
            [
                f"Seek clarification when price / GC estimate is outside {policy['low']} to {policy['high']}."
            ],
            [f"Minimum warranty: {policy['min_years']} years."],
        ]
        rule = {
            "Lowest submitted price": "Rank eligible bids by submitted price.",
            "Lowest eligible leveled cost": "Rank eligible bids by leveled cost including scope plugs.",
            "Budget ceiling": f"Apply a USD {policy['budget']} ceiling, then minimize leveled cost.",
            "Schedule priority": f"Require completion within {policy['deadline']} days, then minimize leveled cost.",
            "Weighted best value": f"Weight relative lowest cost at {policy['weight']} percent and relative fastest duration for the balance.",
            "Best value within window": f"Shortlist all eligible bidders within {policy['window']} percent of the lowest leveled cost.",
            "Split or combined packages": "Minimize combined package price, cover all lots exactly once and honor bundle conditions.",
            "Warranty-adjusted cost": f"Minimize leveled cost plus expected retained repair cost for {policy['beneficiary']}. Claim probability {policy['probability']} in year {policy['event_year']}, repair cost USD {policy['repair']}, requiring {policy['event_coverage']}. Apply coverage caps and deductibles.",
        }
        write_document(
            folder / policy_file, "Award policy", clauses + [[rule[policy["template"]]]]
        )
    for d in [*run["files"], dict(file=policy_file, kind="award_policy")]:
        name = d["file"]
        if name in state["documents"]:
            continue
        with (folder / name).open("rb") as f:
            result = call(
                "POST",
                base + "/documents",
                files={"file": (name, f)},
                data={"kind": d["kind"]},
            )
        state["documents"][name] = result["id"]
        save(path, state)
    if not state.get("scope_ready"):
        call("POST", base + "/scope/generate")
        state["scope_ready"] = True
        save(path, state)
    call("POST", base + "/level", json={"forceExtract": False})
    return path
