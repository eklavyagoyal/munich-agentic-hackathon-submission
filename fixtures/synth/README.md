# Synthetic fixtures — no QuantCo data in here

Every file in this directory was written by hand for testing. None of it comes from
the organisers' case archives, and none of it could have: the archives are encrypted
and need a per-game key from the API, which this team did not have until 14:30 on
2026-08-22. These fixtures were committed at 12:45 the same day (`4ced048`).

The claim number, the contractor, the street and the town are all invented. Any
resemblance to a real claim is a coincidence of the water-damage genre.

Per Discord (14:35, Hailong@QuantCo): real claim data — invoice PDFs, policies —
must never be committed, on penalty of ranking. Decrypted case files land in
`data/` and `logs/`, both gitignored. Keep it that way:

- never `git add -f` anything under `data/`, `logs/` or `public-cases-ehl/cases/`
- never paste decrypted invoice text into a commit message, an issue, or an agent
  session — agent transcripts are checkpointed to the submission repo
- `tests/test_seams.py` reads `invoices.pdf`; regenerate synthetic cases with
  `tools/make_fixture.py`, never by decrypting a real archive
