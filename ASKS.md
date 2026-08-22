# Open asks

Everything else is built and self-tested. These are the only external blockers.

## From the QuantCo organizers

1. **Our `TEAM_API_KEY`** — registration is in person: team name + Discord handle.

2. **The shared folder link.** The one file we actually need is **`API_HANDBOOK.md`** —
   it defines the submission schema, which is the last thing we are guessing. Also in
   there: `starter_script.py`, `pixi.toml`, case 0, and the encrypted case zips.
   → unblocks `c2f/api.py` (three endpoint paths and one payload shape, all marked ⚠️)

3. **Do you provide an `OPENAI_KEY`, or do we bring our own LLM key?** The starter
   script reads one from the environment but does not say who supplies it.
   → we support both providers already; we just need one key to exist

4. **Are per-line-item transaction outcomes available via the API, or only in the
   leaderboard UI?** Per round and line item we want: accepted/rejected, what we were
   paid as issuer, what we paid as insurer.
   → this is the only channel that reveals the hidden threshold. A rejection tells us
   which side of `t` we were on; an acceptance tells us nothing. Without it we cannot
   detect systematic bias, and systematic bias is invisible from the standings alone.
   → unblocks `c2f/calibrate.py` (the fit works; only the input adapter is guessed)

5. **Round schedule** — first case time, cadence, when the tournament ends, and whether
   it runs overnight. Determines whether we need a rota; a missed round is worse than a
   sloppy one.

6. **Any rate limit on the decryption-key endpoint?** We intend to poll it at case
   release and would rather not look like we are hammering it.

Worth confirming while you are there, though the handbook probably covers them:

- Must every line item appear in the submission, or may we omit rows?
- Are line items keyed by the printed position number?
- Gross totals in EUR with cents — decimals accepted?
- Is the absolute floor on the payment cap `c` published?

## From the team building the modular layer

7. **Which of these does your layer own:** decrypt · PDF extraction · submission ·
   scheduling? We currently have all four in `run.py` / `c2f/api.py` and will delete
   whatever you cover rather than merge duplicates.

8. **Do you call Python in-process or shell out?** Both are supported
   (`c2f.predict.predict()` / `python -m c2f.predict --json`) — we just want to drop the
   one you do not use. See the integration contract in README.md.

9. **Where do decrypted case files land on disk?** `predict()` takes a folder and sniffs
   `policy.txt` / `description.txt` / `*.pdf` / images, with keyword fallback on the
   filenames. If your naming differs, tell us and we will match it.

## Local setup, whoever runs the rounds

```bash
brew install poppler p7zip
```

`pdftotext` is present on this machine; `7z` is not, and the live path needs it.
