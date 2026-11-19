# Bid set generator

## Install and start

From the repository root on macOS, install uv (for example with `brew install uv`), then run:

```sh
uv python install 3.12
./simulator/install.sh
./simulator/run.sh
```

Open http://localhost:8501. Stop with Ctrl-C. Repeatable fixture generation works locally. For Gemini-assisted scenarios and proposal wording, set GEMINI_KEY, GEMINI_MODEL and optionally GEMINI_HIGHER_MODEL in the repository-root .env before starting. Install LibreOffice for paginated Word previews. The built-in text preview is available without it.

## Give a tester a bid set

1. Open **Create bid set**. Choose **Roofing stress test**, leave the six invitees as shown and select **Repeatable fixture**. Click **Generate bid set**.
2. **Expected answers** opens automatically. Choose **Lowest eligible leveled cost** to see Alder Works win. Choose **Warranty-adjusted cost** to see Birch Assembly win under the default risk assumptions.
3. **Download bid set (ZIP)** contains GC inputs, the selected award policy and bidder documents. **Download expected answers** produces a separate plain-text key with the expected award, bidder eligibility, amounts and document checks.
4. Use **Preview bid documents** to inspect an artifact. Use **Save policy version** to keep your rules for another session. Changing the template and downloading again pairs the same bids with the new policy.
5. Give the ZIP to the person running the test and the key to the person checking results. Select an earlier set in **Saved bid set** to revisit it.

[Illustrated usage guide](../docs/Bid-Leveling-Simulator-User-Guide.pdf)
