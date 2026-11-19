"""Streamlit project authoring and package-level expected answers."""

from copy import deepcopy
import json

import pandas as pd
import streamlit as st

import complications as comp
import core
import project as pr


def builder(models, saved=None):
    if "project_draft" not in st.session_state:
        st.session_state.project_draft = pr.starter()
    project = st.session_state.project_draft
    version = st.session_state.get("project_version", 0)

    def apply():
        st.session_state.project_version = version + 1
        st.rerun()

    st.header("Create project bid set")
    with st.expander("Choose a project starter"):
        template = st.selectbox(
            "Project starter", ["TCJC · 45 packages", "School Expansion · 3 packages"]
        )
        if st.button("Replace draft with selected starter"):
            st.session_state.project_draft = (
                pr.starter() if template.startswith("TCJC") else pr.school_demo()
            )
            st.session_state.package_index = 0
            apply()
    if saved and "project" in saved and st.button("Clone selected project"):
        st.session_state.project_draft = deepcopy(saved["project"])
        apply()
    project["name"] = st.text_input(
        "Project name", project["name"], key=f"project-name{version}"
    )
    packages = project["packages"]
    st.caption(f"{len(packages)} packages in this project.")
    index = st.selectbox(
        "Trade package",
        range(len(packages)),
        format_func=lambda i: packages[i]["code"] + " · " + packages[i]["trade"],
        key=f"project-package{version}",
        index=min(st.session_state.get("package_index", 0), len(packages) - 1),
    )
    st.session_state.package_index = index
    pkg = packages[index]
    key = f"project-{version}-{index}"
    options = [pr.BID, pr.GC_COST, pr.REMOVED]
    pkg["treatment"] = st.selectbox(
        "Package treatment",
        options,
        index=options.index(pkg.get("treatment", pr.BID)),
        key=key + "treatment",
    )
    if pkg["treatment"] != pr.BID:
        st.info(
            "Generation supplies GC evidence for this package and skips invitations and proposals. Choose Solicit bids to exercise bidder scenarios for it."
        )
    if pr.project_costs(project):
        with st.expander("Project estimate summary"):
            st.caption(
                "Package budgets come from the TCJC Estimate Summary. The starter distributes each budget across representative scope items for testing. Changes to those estimates update the allowance."
            )
            rows = [
                {
                    "Package": p["code"],
                    "Description": p["trade"],
                    "Basis": p.get("treatment", pr.BID),
                    "Estimate (USD)": pr.package_estimate(p),
                }
                for p in packages
            ]
            rows.extend(
                {"Package": "", "Description": n, "Basis": b, "Estimate (USD)": v}
                for n, b, v in pr.project_costs(project)
            )
            st.dataframe(rows, hide_index=True)
    with st.expander("Manage trade packages"):
        left, right = st.columns(2)
        new_code = left.text_input("Package code", pkg["code"], key=key + "code")
        new_name = right.text_input("Trade name", pkg["trade"], key=key + "trade")
        a, b, d, e = st.columns(4)
        action = next(
            (
                name
                for name, button in zip(
                    ["Rename", "Add", "Duplicate", "Remove"],
                    [
                        a.button("Rename package"),
                        b.button("Add package"),
                        d.button("Duplicate package"),
                        e.button("Remove package", disabled=len(packages) == 1),
                    ],
                )
                if button
            ),
            None,
        )
        if action:
            if action == "Remove":
                packages.pop(index)
            else:
                if (
                    not new_code.strip()
                    or not new_name.strip()
                    or any(
                        other["code"].lower() == new_code.lower()
                        for other in packages
                        if action != "Rename" or other is not pkg
                    )
                ):
                    raise ValueError("Enter a distinct package code and a trade name.")
                if action == "Rename":
                    pkg.update(code=new_code, trade=new_name)
                else:
                    added = (
                        deepcopy(pkg)
                        if action == "Duplicate"
                        else pr.package(
                            new_code,
                            new_name,
                            [("New scope item", 1, "LS", 1000)],
                            ["New firm"],
                        )
                    )
                    added.update(code=new_code, trade=new_name)
                    packages.append(added)
                    st.session_state.package_index = len(packages) - 1
            apply()

    with st.expander("GC scope sheet"):
        with st.form(key + "items"):
            edited = st.data_editor(
                pd.DataFrame(pkg["items"]),
                hide_index=True,
                num_rows="dynamic",
                key=key + "itemsgrid",
            )
            if st.form_submit_button("Apply GC scope items"):
                items = json.loads(edited.to_json(orient="records"))
                ids = [i["id"] for i in items]
                if (
                    not ids
                    or not all(isinstance(k, str) and k.strip() for k in ids)
                    or len(ids) != len(set(ids))
                ):
                    raise ValueError("Each scope item needs a distinct text ID.")
                for item in items:
                    if not item["description"] or not item["unit"]:
                        raise ValueError("Enter an item description and unit.")
                    pr.number(item["quantity"], "Quantity")
                    if item["estimate"] is not None:
                        pr.number(item["estimate"], "Estimate")
                for bidder in pkg["bidders"]:
                    bidder["coverage_map"] = {
                        i["id"]: bidder["coverage_map"].get(i["id"], pr.cell(i))
                        for i in items
                    }
                pkg["items"] = items
                apply()
    bidders = pkg["bidders"]
    idx = st.selectbox(
        "Invited subcontractor",
        range(len(bidders)),
        format_func=lambda i: bidders[i]["firm"],
        key=key + "bidder",
    )
    b = bidders[idx]
    with st.expander("Manage invitees and bid terms"):
        name = st.text_input("Company name", b["firm"], key=key + str(idx) + "name")
        l, r = st.columns(2)
        if l.button("Add invitee"):
            if not name.strip() or any(
                x["firm"].lower() == name.lower() for x in bidders
            ):
                raise ValueError("Enter a new company name.")
            bidders.append(pr.new_bidder(name, pkg["items"], len(bidders)))
            apply()
        if r.button("Remove invitee", disabled=len(bidders) == 1):
            bidders.pop(idx)
            apply()
        with st.form(key + str(idx) + "terms"):
            response = st.selectbox(
                "Response", core.RESPONSES, index=core.RESPONSES.index(b["response"])
            )
            fmt = st.selectbox(
                "Document format", core.FORMS, index=core.FORMS.index(b["format"])
            )
            lump = st.number_input(
                "Priced lump sum (USD)",
                min_value=0.0,
                value=float(b.get("lump_sum", 0)),
            )
            post, tax, sdi = st.columns(3)
            amounts = [
                col.number_input(label, min_value=0.0, value=float(b[field]))
                for col, label, field in [
                    (post, "Post-bid adjustment (USD)", "post_bid"),
                    (tax, "Sales tax (USD)", "tax"),
                    (sdi, "SDI (USD)", "sdi"),
                ]
            ]
            if st.form_submit_button("Apply bidder terms"):
                if not name.strip() or any(
                    x is not b and x["firm"].lower() == name.lower() for x in bidders
                ):
                    raise ValueError("Enter a distinct company name.")
                b.update(
                    firm=name,
                    lump_sum=lump,
                    response=response,
                    format=fmt,
                    post_bid=amounts[0],
                    tax=amounts[1],
                    sdi=amounts[2],
                )
                apply()
    st.subheader("Item coverage")
    items = pkg["items"]
    cells = b["coverage_map"]
    selected = st.multiselect(
        "Items offered",
        [i["id"] for i in items],
        format_func=lambda k: next(i["description"] for i in items if i["id"] == k),
        key=key + str(idx) + "selected",
    )
    l, r = st.columns(2)
    all_items = l.button("Price all items")
    if all_items or r.button("Price selected items", disabled=not selected):
        for i in items:
            cells[i["id"]]["status"] = (
                "Priced" if all_items or i["id"] in selected else "Excluded"
            )
        apply()
    with st.form(key + str(idx) + "matrix"):
        rows = [
            dict(ID=i["id"], Item=i["description"], **cells[i["id"]]) for i in items
        ]
        changes = st.data_editor(
            pd.DataFrame(rows),
            hide_index=True,
            disabled=["ID", "Item"],
            column_config={
                "status": st.column_config.SelectboxColumn(
                    "Confirm", options=pr.STATES, required=True
                ),
                "amount": st.column_config.NumberColumn("Quoted value", min_value=0.0),
                "carrying": st.column_config.SelectboxColumn(
                    "Included in item",
                    options=["", "Lump sum"] + [i["id"] for i in items],
                ),
                "allowance": st.column_config.NumberColumn(
                    "GC allowance override", min_value=0.0
                ),
            },
        )
        if st.form_submit_button("Apply coverage"):
            for v in json.loads(changes.to_json(orient="records")):
                k = v.pop("ID")
                v.pop("Item")
                cells[k] = v
            apply()
    st.caption(
        "Apply grid edits before switching firms or generating. Exclusions use the GC estimate unless overridden. Unanswered required items need clarification."
    )
    with st.expander("Scenario complications"):
        settings = project.setdefault("complications", {})
        enabled = st.multiselect(
            "Scenarios to generate",
            list(comp.OPTIONS),
            default=list(settings),
            key=f"scenario-list{version}",
        )
        for name in list(settings):
            if name not in enabled:
                del settings[name]
        for name in enabled:
            cfg = settings.setdefault(name, dict(comp.OPTIONS[name]))
            st.markdown(f"**{name}**")
            st.caption(comp.QUESTIONS[name])
            for field, default in comp.OPTIONS[name].items():
                value = cfg.get(field, default)
                widget_key = f"scenario-{version}-{name}-{field}"
                label = field.replace("_", " ").title()
                opts = comp.choices(name, field)
                if opts:
                    cfg[field] = st.selectbox(
                        label, opts, index=opts.index(value), key=widget_key
                    )
                elif field in ("demolition", "earthwork", "package", "second_package"):
                    options = {p["code"]: p["trade"] for p in packages}
                    if value not in options:
                        options[value] = "Unavailable"
                    cfg[field] = st.selectbox(
                        label,
                        list(options),
                        index=list(options).index(value),
                        format_func=lambda k, names=options: k + " · " + names[k],
                        key=widget_key,
                    )
                elif isinstance(default, str):
                    cfg[field] = st.text_input(label, value, key=widget_key)
                else:
                    cfg[field] = st.number_input(label, value=value, key=widget_key)
    problem = ""
    if settings:
        try:
            for candidate in comp.compile_draft(project):
                pr.prepare(candidate, project["name"])
        except (ValueError, KeyError) as exc:
            problem = str(exc)
            st.error(problem)
    with st.expander("Advanced project JSON"):
        value = st.text_area(
            "Edit project, including warranties, attachments, price overrides and lot offers",
            json.dumps(project, indent=2),
            key=key + "json",
        )
        if st.button("Apply project JSON"):
            parsed = json.loads(value)
            if not parsed["packages"]:
                raise ValueError("Include at least one package.")
            for p in parsed["packages"]:
                pr.prepare(p, parsed["name"])
            st.session_state.project_draft = parsed
            apply()
    draft = st.radio(
        "Document drafting", ["Repeatable fixture", "Gemini"], horizontal=True
    )
    if st.button("Generate project bid set", type="primary", disabled=bool(problem)):
        with st.spinner("Writing project documents"):
            st.session_state.selected = pr.generate(project, models, draft == "Gemini")
        st.session_state.open_answers = True
        st.rerun()


def answers(folder, run, policy_form, preview):
    st.header(run["project"]["name"] + " · Expected answers")
    path = folder / "active-policies.json"
    policies = core.read(path) if path.exists() else {}
    code = st.selectbox(
        "Package policy and tally",
        list(run["packages"]),
        format_func=lambda k: k + " · " + run["packages"][k]["trade"],
    )
    if run["packages"][code]["bidders"]:
        with st.expander("Edit package award policy"):
            policy = policy_form(
                package_code=code, initial=policies.get(code, pr.DEFAULT_POLICY)
            )
            if st.button("Save package policy version"):
                core.save(
                    folder / ("award-" + code + "-" + core.uuid4().hex[:8] + ".json"),
                    dict(policy=policy),
                )
                policies[code] = policy
                core.save(path, policies)
        policies[code] = policy
    summary, coverage, tallies = pr.results(run, policies)
    st.subheader("Estimate Summary")
    st.dataframe(summary, hide_index=True)
    checks = comp.checks(run, summary, tallies)
    if checks:
        st.subheader("Scenario checks")
        st.dataframe(checks, hide_index=True)
    st.subheader("Bid Tally Sheet · " + code)
    if not tallies[code]:
        st.info(
            run["packages"][code]["treatment"] + ". No subcontract award is expected."
        )
    else:
        table = pd.DataFrame(tallies[code]).rename(
            columns={
                "post_bid": "Post-bid adjustment",
                "tax": "Sales tax",
                "sdi": "SDI",
            }
        )
        table["Rank"] = table["Rank"].astype(str)
        st.dataframe(
            table[
                [
                    "Rank",
                    "Bidder",
                    "Status",
                    "Submitted",
                    "Plug",
                    "Base bid value",
                    "Post-bid adjustment",
                    "Subcontract value",
                    "Sales tax",
                    "SDI",
                    *(
                        ["GC costs to complete"]
                        if "GC costs to complete" in table
                        else []
                    ),
                    "Total package value",
                    *(["Exposure", "Adjusted"] if "Adjusted" in table else []),
                ]
            ].style.map(
                lambda r: (
                    "background-color: #c4ead4; color: #12452a" if r == "1" else ""
                ),
                subset=["Rank"],
            ),
            hide_index=True,
        )
        items = run["packages"][code]["scope_lines"]
        item = st.selectbox(
            "Compare bidder coverage for item",
            items,
            format_func=lambda i: i["description"],
        )
        st.dataframe(
            [
                v
                for v in coverage
                if v["Package"] == code and v["Item ID"] == item["id"]
            ],
            hide_index=True,
        )
    z, w = pr.exports(folder, run, policies, summary, coverage, tallies)
    l, r = st.columns(2)
    l.download_button("Download project bid set (ZIP)", z, folder.name + "-bids.zip")
    r.download_button(
        "Download tester’s answer key (Excel)", w, folder.name + "-answers.xlsx"
    )
    with st.expander("Preview package documents"):
        preview([d for d in run["files"] if d["package"] == code])
