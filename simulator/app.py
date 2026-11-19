import json
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import pandas as pd
import streamlit as st

import core as c
from award_policy import policy_text
from ranking import rank_bids

st.set_page_config(page_title="Bid day simulator", layout="wide")
st.title("Bid set generator")
if st.session_state.pop("open_answers", False):
    st.session_state.workspace = "Expected answers"
    st.session_state.bid_set_id = st.session_state.selected
page = st.sidebar.radio(
    "Workspace",
    ["Create bid set", "Expected answers"], key="workspace",
)
ids = sorted(
    [p.name for p in c.RUNS.iterdir() if (p / "run.json").exists()], reverse=True
)
rid = st.sidebar.selectbox(
    "Saved bid set",
    options=ids, key="bid_set_id",
    index=ids.index(st.session_state.selected)
    if st.session_state.get("selected") in ids
    else 0,
)
folder = c.RUNS / rid if rid else None
run = c.read(folder / "run.json") if folder else None
guide = c.ROOT / "docs/Bid-Leveling-Simulator-User-Guide.pdf"
if guide.exists():
    st.sidebar.download_button("Usage guide (PDF)", guide.read_bytes(), guide.name)
models = {}
with st.sidebar.expander("Stage models"):
    tiers = list(dict.fromkeys(c.MODELS.values()))
    for stage in ("scenario", "generation"):
        default = c.MODELS[stage]
        models[stage] = st.selectbox(
            stage.title(), tiers, index=tiers.index(default), key="model_" + stage
        )


def builder():
    st.header("Create bid set")
    names = [
        "Roofing stress test",
        "Revision and partial scope",
        "All regrets",
        "All unrelated",
        "Document extraction stress",
        "Split award",
    ]
    source = st.selectbox(
        "Starting point", names + (["Clone selected bid day"] if run else [])
    )
    key = (source, rid if source.startswith("Clone") else "")
    if st.session_state.get("source") != key:
        st.session_state.source = key
        st.session_state.spec = json.dumps(
            run["scenario"] if source.startswith("Clone") else c.preset(source),
            indent=2,
        )
    with st.expander("Describe a scenario"):
        prompt = st.text_area("Bid day instructions")
        if st.button("Interpret with Gemini", disabled=not prompt):
            sample = c.preset(names[0])
            result = c.ask(
                "scenario",
                models,
                "Return a JSON string containing a scenario with exactly this structure. "
                + json.dumps(sample)
                + " Allowed responses: "
                + str(c.RESPONSES)
                + "; formats: "
                + str(c.FORMS)
                + "; match: Full, Partial, Unrelated. Request: "
                + prompt,
                {
                    "type": "object",
                    "properties": {"scenario": {"type": "string"}},
                    "required": ["scenario"],
                },
            )
            parsed = json.loads(result["scenario"])
            c.validate(parsed)
            st.session_state.spec = json.dumps(parsed, indent=2)
    with st.expander("Choice catalog and advanced scenario editor"):
        query = st.text_input("Search choices")
        for label, values in {
            "Response history": c.RESPONSES,
            "Scope relationship": ["Full", "Partial", "Unrelated"],
            "Format": c.FORMS,
            "Price": [
                "0.01×",
                "100×",
                "custom multiplier",
                "line quantity",
                "line rate",
                "line extension",
                "plug",
            ],
            "Terms": [
                "coverage",
                "duration",
                "deductible",
                "cap",
                "schedule",
                "free-text exclusions",
                "commercial conditions",
            ],
        }.items():
            if query.lower() in (label + str(values)).lower():
                st.write(label + " — " + ", ".join(values))
        st.text_area("Scenario JSON", key="spec", height=260)
    s = json.loads(st.session_state.spec)
    version = hash(st.session_state.spec)
    a, b, d = st.columns([2, 1, 1])
    s["name"] = a.text_input("Scenario name", s["name"], key=f"name{version}")
    s["trade"] = b.text_input("Trade", s["trade"], key=f"trade{version}")
    s["estimate"] = d.number_input(
        "GC estimate (USD)",
        value=float(s["estimate"]),
        min_value=0.01,
        key=f"est{version}",
    )
    s["scope"] = st.text_input("Requested scope", s["scope"], key=f"scope{version}")
    st.subheader("Invited subcontractors")
    st.caption(
        "Edit the grid. Scroll right for warranty, schedule and terms. Use the advanced editor for individual quote lines."
    )
    rows = [
        {k: v for k, v in b.items() if k not in ("lines", "attachments", "offers")}
        for b in s["bidders"]
    ]
    lines = {b["firm"]: b.get("lines", []) for b in s["bidders"]}
    options = {
        "layout": ["Standard", "Scanned", "Late total", "Uncached formula"],
        "response": c.RESPONSES,
        "format": c.FORMS,
        "match": ["Full", "Partial", "Unrelated"],
        "coverage": ["Materials only", "Labor and materials", "None"],
    }
    edited = st.data_editor(
        pd.DataFrame(rows),
        num_rows="dynamic",
        hide_index=True,
        key=f"bids{version}",
        column_config={
            k: st.column_config.SelectboxColumn(options=v, required=True)
            for k, v in options.items()
        },
    )
    attachments = {b["firm"]: b.get("attachments", []) for b in s["bidders"]}
    offers = {b["firm"]: b.get("offers", []) for b in s["bidders"]}
    s["bidders"] = [
        dict(
            b,
            offers=offers.get(b["firm"], []),
            lines=lines.get(b["firm"], []),
            attachments=attachments.get(b["firm"], []),
        )
        for b in edited.to_dict("records")
    ]
    mode = st.radio(
        "Document drafting", ["Gemini", "Repeatable fixture"], horizontal=True
    )
    if st.button("Generate bid set", type="primary"):
        with st.spinner("Writing bid documents"):
            st.session_state.selected = c.generate(s, models, mode == "Gemini")
        st.session_state.open_answers = True
        st.rerun()


def documents():
    docs = run["files"]
    d = st.selectbox("Artifact", docs, format_func=lambda x: x["title"])
    path = folder / d["file"]
    original = folder / d.get("original", d["file"])
    st.download_button("Download original", original.read_bytes(), original.name)
    if path.suffix == ".pdf":
        st.pdf(path.read_bytes())
    elif path.suffix == ".xlsx":
        wb = c.load_workbook(path, read_only=True)
        sheet = st.selectbox("Sheet", wb.sheetnames)
        ws = wb[sheet]
        st.dataframe(pd.DataFrame(ws.values).fillna(""), hide_index=True)
        addr = st.text_input("Inspect cell", "A1")
        st.write("Stored formula or value", ws[addr].value)
        wb.close()
        wb = c.load_workbook(path, read_only=True, data_only=True)
        st.write("Cached value", wb[sheet][addr].value)
        wb.close()
    else:
        output = c.office_pdf(path, folder / "previews")
        if output:
            st.pdf(output.read_bytes())
        else:
            st.caption("Word content preview · install LibreOffice for pagination.")
            st.text(c.ingest.read(path)["text"])
def policy_form():
    existing = sorted(folder.glob("award-*.json"))
    choice = st.selectbox("Start from", ["New policy"] + [p.name for p in existing])
    defaults = {} if choice == "New policy" else c.read(folder / choice)["policy"]
    key = rid + choice
    template = st.selectbox(
        "Award template",
        c.POLICIES,
        index=c.POLICIES.index(defaults.get("template", c.POLICIES[0])),
        key="template" + key,
    )
    p = {"template": template}
    p["label"] = st.text_input(
        "Version name", defaults.get("label", template), key="label" + key + template
    )
    with st.expander("Eligibility, scoring and warranty assumptions"):
        controls = [
            ("low", "Minimum price multiplier", 0.05),
            ("high", "Maximum price multiplier", 10.0),
            ("min_years", "Minimum warranty (years)", 0.0),
            ("budget", "Budget ceiling (USD)", 550000.0),
            ("deadline", "Schedule limit (days)", 60.0),
            ("window", "Best-value window (%)", 3.0),
            ("weight", "Price weight (%)", 70.0),
            ("event_year", "Year of claim", 5.0),
            ("probability", "Probability of claim", 0.1),
            ("repair", "Present-value repair cost (USD)", 100000.0),
        ]
        for field, label, default in controls:
            p[field] = st.number_input(
                label,
                value=float(defaults.get(field, default)),
                min_value=0.0,
                max_value={"weight": 100.0, "probability": 1.0}.get(field),
                key=key + field,
            )
        p["event_coverage"] = st.selectbox(
            "Coverage required for recovery",
            ["Labor and materials", "Materials only"],
            index=int(defaults.get("event_coverage") == "Materials only"),
            key=key + "coverage",
        )
        p["beneficiary"] = st.text_input(
            "Party bearing retained cost",
            defaults.get("beneficiary", "Owner"),
            key=key + "beneficiary",
        )
    if p["low"] > p["high"]:
        raise ValueError("Minimum price multiplier exceeds maximum.")
    return p


def awards():
    st.header("Expected answers")
    s = run["scenario"]
    st.caption(f"{s['name']} · {s['trade']} · GC estimate USD {s['estimate']:,.2f}")
    p = policy_form()
    rows, outcome = c.evaluate(s, p)
    st.metric("Expected award", outcome)
    basis = rank_bids(rows, p["template"])
    ordered = sorted(rows, key=lambda r: r["Rank"] if isinstance(r["Rank"], int) else float("inf"))
    table = pd.DataFrame(ordered, columns=["Rank", "Bidder", "Status", "Submitted", "Leveled", "Exposure", "Adjusted", "Days"] + (["Score"] if basis == "Score" else []))
    table["Rank"] = table["Rank"].astype(str)
    def rank_color(value):
        if value == "1":
            return "background-color: #c4ead4; color: #12452a"
        if value.isdigit():
            return "background-color: #deecfa; color: #193f64"
        return "background-color: #edf0f2; color: #35414b"
    st.dataframe(table.style.map(rank_color, subset=["Rank"]), hide_index=True)
    if p["template"] == "Split or combined packages":
        st.caption("Package offers are evaluated together. The expected award lists the selected combination.")
    else:
        st.caption(f"Rank 1 leads on {basis.lower()}. Tied bids share a rank. Status explains each unranked bid.")

    policy_document = policy_text(p)
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as archive:
        for doc in run["files"]:
            archive.write(folder / doc["file"], doc["file"])
        archive.writestr("GC-award-policy.txt", policy_document)
    answer = [s["name"], "Bid set " + rid, policy_document, "Expected award: " + outcome, "", "Bidder checks (USD)"]
    for bidder, row in zip(s["bidders"], rows):
        answer.extend(["", bidder["firm"] + " — " + row["Status"],
            f"Response: {bidder['response']}. Scope offered: {bidder['scope']}. Scope relationship: {bidder['match']}." if bidder["response"] not in ("Silent","Regret") else "Response: "+bidder["response"],
            " | ".join(f"{k}: {v}" for k,v in row.items() if k not in ("Bidder","Status") and v is not None)])
        if row["Leveled"] is not None:
            answer.append(f"Warranty: {bidder['coverage']}, {bidder['years']} years; deductible {bidder['deductible']}, cap {bidder['cap']}.")
    answer.extend(["", "Document checks"])
    for doc in run["files"]:
        answer.append(doc["file"]+" — "+doc["title"]+" "+json.dumps(doc.get("expected") or {}))
    left,right = st.columns(2)
    left.download_button("Download bid set (ZIP)",zip_buffer.getvalue(),rid+"-bid-set.zip",mime="application/zip")
    right.download_button("Download expected answers", "\n".join(answer),rid+"-expected-answers.txt")
    st.caption("Use the ZIP as the test input. Give the separate answer key to the tester.")
    with st.expander("Preview bid documents"):
        documents()
    if st.button("Save policy version", type="primary"):
        c.save(
            folder / ("award-" + c.uuid4().hex[:10] + ".json"),
            dict(policy=p, outcome=outcome, rows=rows),
        )
        st.success("Saved " + p["label"])
    for f in sorted(folder.glob("award-*.json")):
        record = c.read(f)
        st.write(record["policy"]["label"] + " — " + record["outcome"])


try:
    if page == "Create bid set":
        builder()
    elif run:
        awards()
    else:
        st.info("Open Create bid set and click Generate bid set to see its expected answers.")
except Exception as exc:
    st.error(str(exc))
