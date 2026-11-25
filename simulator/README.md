# Bid set generator

## Install and start

From the repository root on macOS, install uv (for example with `brew install uv`), then run:

```sh
uv python install 3.12
./simulator/install.sh
./simulator/run.sh
```

Open http://localhost:8501. Stop with Ctrl-C. Repeatable fixture generation works locally. For Gemini-assisted scenarios and proposal wording, set GEMINI_KEY, GEMINI_MODEL and optionally GEMINI_HIGHER_MODEL in the repository-root .env before starting. Install LibreOffice for paginated Word previews. The built-in text preview is available without it.

## Generate a large TCJC bid set

1. Open **Create bid set → Large TCJC bid set**. Set **Bid items per solicited trade** (4–30) and **Bidding firms per solicited trade** (2–20). These counts apply to all 42 solicited trades.
2. Select a package under **Preview scope for trade**. The preview shows its individual items. Click **Generate all 45 packages** to create the full set locally.
3. At the defaults (12 items and eight firms), expect **504 bid items**, **336 current proposals**, **42 superseded quotes** and **42 regret letters**. The two GC-carried packages and the removed scope produce GC records.
4. On **Expected answers**, choose a package and compare coverage for one item. Download the **project ZIP** for the leveling app and the **Excel answer key** for the tester. For the default Electrical example, filter **Item Coverage** to **26.00 / I03 / Birch Electrical** and trace the exclusion to the proposal listed under **Evidence**.

[Illustrated large-set walkthrough and simulator guide (PDF)](../docs/Bid-Leveling-Simulator-User-Guide.pdf)

## Generate a whole project

1. Choose **Whole project**. New drafts start with all 45 coded packages from the TCJC Estimate Summary. Type a package code or name in **Trade package** to find it. **Project estimate summary** shows the budgets, included SDI and a document completion allowance calculated at 1% of active package estimates. The bundled catalog supplies the original budgets. Scope items are representative and the item allocations, bidders and proposals are test fixtures. Package 13.49 was removed in the workbook and generates a GC scope withdrawal. General Conditions (99.10) and Winter Conditions Allowance (99.15) generate GC cost estimates. Change **Package treatment** to solicit subcontract bids for any of these. To restore the full catalog in an existing session, open **Choose a project starter**, select **TCJC · 45 packages**, and click **Replace draft with selected starter**. This replaces unsaved draft edits. The three-package School Expansion example remains available there.
2. Select a trade. Open **GC scope sheet** to edit its items. Under **Manage trade packages**, enter a unique code and name to add or duplicate a package. Under **Manage invitees and bid terms**, enter a new company name to invite another bidder or edit the current bidder’s terms.
3. Choose a firm and set **Item coverage**. Price all items, price a selected subset, or edit each cell. An inclusion references a priced item ID or priced lump sum. Exclusions carry the item estimate or a GC allowance override. A blank allowance on an excluded item with no estimate needs clarification. Choose **Apply coverage** before switching firms.
4. Generate the project. On **Expected answers**, select Electrical, then **BDA / First Responder DAS testing and rough-in**. Alder prices it, Birch includes it in I01, Cedar excludes it, and Dune leaves it unanswered. The documents reflect those four outcomes. The GC adjustment sheet supplies the allowance used to level Cedar. Dune remains unranked pending clarification.
5. Change or save the award policy per package. Download the **project ZIP** for the leveling app and the **Excel answer key** for the tester. The workbook contains Estimate Summary, package tally sheets, Item Coverage, Documents, and Policies. Optional alternates have their own sheet when present. Adjusted cost and Exposure appear only on warranty-adjusted tallies.
6. For advanced scenarios use **Advanced project JSON**. Each bidder may have a `submitted_override`, `alternates` with description and amount, a warranty, attachments or lot offers. Set package `lots` and bidder `offers` for split awards. Use the **Single trade** workflow for plain-English scenario interpretation.

## Generate a single trade

1. Open **Create bid set**. Choose **Single trade**, then **Roofing stress test**, leave the six invitees as shown and select **Repeatable fixture**. Click **Generate bid set**.
2. **Expected answers** opens automatically. Choose **Lowest eligible leveled cost** to see Alder Works win. Choose **Warranty-adjusted cost** to see Birch Assembly win under the default risk assumptions.
3. **Download bid set (ZIP)** contains GC inputs, the selected award policy and bidder documents. **Download expected answers** produces a separate plain-text key with the expected award, bidder eligibility, amounts and document checks.
4. Use **Preview bid documents** to inspect an artifact. Use **Save policy version** to keep your rules for another session. Changing the template and downloading again pairs the same bids with the new policy.
5. Give the ZIP to the person running the test and the key to the person checking results. Select an earlier set in **Saved bid set** to revisit it.


## Choose proposal styles

Real proposals rarely look alike. **Proposal styles**, next to **Document drafting** in all three workflows, controls how bidder proposals are laid out.

- **Standard** prints every proposal in the same simple layout. Existing bid sets keep this layout.
- **Realistic mix** gives each bidder one of these layouts, picked from the project, trade and firm names, so the same set regenerates the same way:

| Style | Formats | What makes it hard to read | Line prices |
|---|---|---|---|
| **GC bid form** | pdf | A multi-page GC "Attachment 2" filled in by the bidder. Filled values are a separate text layer, as in a flattened PDF form, so text extraction returns them apart from their labels. The form also has the GC's own scope list, labor rates and blank or N/A fields. A blank price cell means the item is not mentioned. | Yes |
| **Formal** | pdf, docx | The price is in a sentence ("All for the net sum of …"), with an optional bond add, long exclusion lists and a terms page full of numbers that are not prices. | No |
| **Structured quote** | pdf, docx, xlsx | A quote table with section subtotals, a "Total with add alternates" row and a sales tax line. The xlsx version has a summary block, merged cells and two empty sheets. | Yes |
| **Technical** | pdf, docx | A long list of scope bullets and general notes with one total, plus labor rates. | No |
| **Informal** | pdf | An estimate-tool printout. Layered header text reads back as duplicated fragments, and the validity date has the wrong year. Realistic mix delivers about 3 in 10 as scans with no text layer. | Yes |
| **Vague** | pdf, docx | A short letter with scope bullets, exclusions and one lump sum. In the pdf the total is a separate text layer. | No |
| **Standard** | docx, xlsx, pdf | Today's simple layout | Yes |

To fix one bidder's layout, set **Proposal style** under **Manage invitees and bid terms** (Whole project) or the `style` column (Single trade). **Auto** follows the project setting. Each style lists the formats it supports. The Late total and Uncached formula layouts work only with the Standard style.

Styles change the layout, not the bid. Expected awards and package values are the same as with Standard. When a style shows no line prices, the key shows that bidder's priced items as **Included** in **Lump sum**. Use Standard when you need item-level prices. Formal and Structured quote say the price excludes sales tax, at the rate on the GC adjustments sheet, only when the bidder has a **Sales tax** adder. Without one, they say the price includes tax. Regret letters, superseded quotes and follow-up letters stay in the Standard layout. When any proposal is styled, the answer key adds an **Extraction notes** sheet. It lists each styled document's style, where the price is, whether line prices are shown, which numbers are not prices, and what to watch for. Scanned documents are marked there.

## Exercise optional project scenarios

Open **Scenario complications** on the Whole project page. Every scenario starts off. Select any combination and review the package codes and item IDs before generating. Use the TCJC starter for the supplied examples. The generator applies your scenario settings to a copy of the draft. Conflicting item references must be resolved before generation.

For the backfill walkthrough, select **Shared scope across trades** and leave **Earthwork only** selected. The awarded Earthwork proposal includes BF-01 and the awarded Demolition proposal excludes it. Choose **Both** for an overlap or **Neither** for a gap. Enter an invited firm's name under **Exception firm** to reverse its backfill position and exercise a change of award. **Split excavation and backfill** assigns excavation to Demolition and backfill to Earthwork.

The other choices exercise unclear bid language, partial low bids, GC cost adjustments, signed alternates across trades, component warranties and dated commitments. The ambiguity and low-bid cases target the first invitee. Warranty exceptions apply to the first invitee and other bidders accept the component terms.

Open **Expected answers → Scenario checks** or the Excel sheet of the same name. Each row gives a tester question, the expected result and evidence paths inside the bid ZIP. The reconciliation row rolls up selected package values, project allowances, accepted adjustments and earlier commitments. With a missing award, an unresolved scope gap or an uncertain release overlap, the key shows the known amounts and flags the final balance for clarification. Reapply a package policy to recalculate the checks against the same documents.
