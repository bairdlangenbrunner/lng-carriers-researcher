# directed write: UUID column (2026-09-23)

On Baird's direction in session ("add a UUID column to the very left ... and add maybe 20 unassigned
ones below"), AP §2d, on `data - backend` (gid 243795339):

- inserted a new column A (`UUID`, header in A2, `=column()` in A1 like the rest of row 1);
- one random v4 UUID per existing row (A3:A1231, 1,229 rows, including the stub rows with no row_id);
- appended 20 rows (1232–1251) holding only a pre-generated UUID, unassigned;
- frozen columns 5 → 6 so the same columns stay pinned.

Every existing column moves one letter right (row_id is now column B; row 1 numbers now run 1–50).
No existing value was overwritten. The column dictionaries' INDEX/MATCH ranges shifted automatically.

Deviation from AP §2d item 2: 1,251 new cells can't be shown cell by cell in chat; the full plan
(A1, old = blank, new) is in `plan.csv`. Pre-write guard: row count, column count, frozen count and
the B2 header were rechecked right before writing.

Verification (re-pull): 1250/1250 UUIDs + the A1 formula hold; every pre-existing cell equals the
pre-write pull, shifted one column right. `qc_backend.py`: 7 LOW (pre-existing name checks), none on
the UUID-only rows. Tests: 582 passed.

Revert: `revert.json` (spreadsheets.batchUpdate: delete rows 1232–1251, delete column A, frozen → 5).

Not done: no script keys on UUID yet (row_id is still the batch key), and nothing assigns UUIDs to
future rows automatically. The spare rows are the pool for new vessels.
