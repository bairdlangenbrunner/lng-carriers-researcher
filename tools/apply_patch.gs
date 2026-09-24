/**
 * apply_patch.gs — offset-proof, human-operated applier for LNG-carrier batches.
 *
 * The problem this solves: pasting accepted batch proposals back into the backend
 * by hand can land a value in the wrong column (this is what corrupted rows
 * 1216/1217). This script writes each accepted cell by matching ROW-ID + COLUMN
 * HEADER, so a column offset is impossible — and it previews every change before
 * touching anything.
 *
 * SETUP (one-time):
 *   1. Open the backend Google Sheet → Extensions → Apps Script.
 *   2. Paste this file in. Set BACKEND_SHEET_NAME below to the backend tab's name.
 *   3. Add a tab named exactly "apply_patch" and paste the contents of a batch's
 *      apply_patch.csv into it (cell A1, "Paste special → values only").
 *
 * RUN:
 *   - Run applyPatch() once with DRY_RUN = true. Read the Execution log: it lists
 *     every cell it WOULD set / row it WOULD append, and flags any cell that is
 *     already non-blank.
 *   - When the preview looks right, set DRY_RUN = false and run again to write.
 *
 * The patch format (apply_patch.csv, produced by scripts/apply_batch.py):
 *   op,key,column,value
 *   set,<uuid>,Shipowner country/area,United States    // set a cell on an existing row (key = UUID;
 *                                                     // a legacy "original order" id works while that column exists)
 *   append,C1,Shipowner,MISC Berhad                     // build+append a new row (grouped by key)
 */

// ---- config -----------------------------------------------------------------
var BACKEND_SHEET_NAME = "backend";   // <-- the backend tab's name
var PATCH_SHEET_NAME = "apply_patch"; // tab holding the pasted apply_patch.csv
var ROWID_HEADER = "UUID";           // the column that holds the row key
var LEGACY_ROWID_HEADER = "original order in sheet"; // old key; matched too while the column exists
var DRY_RUN = true;                   // true = preview only; false = actually write
var OVERWRITE_NONBLANK = false;       // set true to allow 'set' to overwrite a non-blank cell

// ---- main -------------------------------------------------------------------
function applyPatch() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var backend = ss.getSheetByName(BACKEND_SHEET_NAME);
  var patchSheet = ss.getSheetByName(PATCH_SHEET_NAME);
  if (!backend) throw new Error("No sheet named '" + BACKEND_SHEET_NAME + "'");
  if (!patchSheet) throw new Error("No sheet named '" + PATCH_SHEET_NAME + "' (paste apply_patch.csv there)");

  var grid = backend.getDataRange().getValues();
  var headerRow = findHeaderRow_(grid);
  if (headerRow < 0) throw new Error("Could not find the header row (needs 'Shipowner' & 'Shipbuilder')");
  var header = grid[headerRow];
  var colOf = {};                     // header string -> 0-based column
  for (var c = 0; c < header.length; c++) if (header[c]) colOf[String(header[c]).trim()] = c;
  var ridCol = colOf[ROWID_HEADER];
  if (ridCol === undefined) throw new Error("No '" + ROWID_HEADER + "' column in the backend header");
  var legacyCol = colOf[LEGACY_ROWID_HEADER];

  var rowOf = {};                     // key (UUID, or legacy id) -> 1-based sheet row
  var spare = [];                     // pre-generated rows: a UUID and nothing else (filled by 'append')
  for (var r = headerRow + 1; r < grid.length; r++) {
    var rid = String(grid[r][ridCol]).trim();
    if (rid) rowOf[rid] = r + 1;
    if (legacyCol !== undefined) {
      var lid = String(grid[r][legacyCol]).trim();
      if (lid && rowOf[lid] === undefined) rowOf[lid] = r + 1;
    }
    var blankRest = true;
    for (var cc0 = 0; cc0 < grid[r].length && blankRest; cc0++)
      if (cc0 !== ridCol && String(grid[r][cc0]).trim() !== "") blankRest = false;
    if (rid && blankRest) spare.push({row: r + 1, uuid: rid});
  }

  var patch = patchSheet.getDataRange().getValues();
  var start = (String(patch[0][0]).trim().toLowerCase() === "op") ? 1 : 0; // skip header row

  var log = [];
  var sets = 0, skips = 0, appends = 0;
  var appendGroups = {};              // key -> { headerString: value }

  for (var i = start; i < patch.length; i++) {
    var op = String(patch[i][0]).trim().toLowerCase();
    var key = String(patch[i][1]).trim();
    var column = String(patch[i][2]).trim();
    var value = patch[i][3];
    if (!op) continue;

    if (op === "set") {
      var sr = rowOf[key], cc = colOf[column];
      if (sr === undefined) { log.push("SKIP set: row_id " + key + " not found"); skips++; continue; }
      if (cc === undefined) { log.push("SKIP set: column '" + column + "' not in header"); skips++; continue; }
      var cur = backend.getRange(sr, cc + 1).getValue();
      var curStr = String(cur).trim();
      // "unknown" is a placeholder, not a value — treat it as blank for overwrite
      // purposes, same as review_app/push.py (_norm(cur).lower() != "unknown").
      var curIsBlank = (cur === "" || cur === null || curStr.toLowerCase() === "unknown");
      if (!curIsBlank && !OVERWRITE_NONBLANK && curStr !== String(value).trim()) {
        log.push("SKIP set (non-blank): row " + key + " · " + column + " has '" + cur + "'"); skips++; continue;
      }
      log.push((DRY_RUN ? "would set " : "set ") + "row " + key + " · " + column + " = '" + value + "'");
      if (!DRY_RUN) {
        var setRange = backend.getRange(sr, cc + 1);
        // Write as literal text: a bare setValue lets Sheets coerce a string like
        // '2026' or '1/2' into a number/date; push.py writes the value raw.
        setRange.setNumberFormat("@");
        setRange.setValue(value);
      }
      sets++;
    } else if (op === "append") {
      if (!appendGroups[key]) appendGroups[key] = {};
      appendGroups[key][column] = value;
    }
  }

  // build + append new rows (one per append-group)
  for (var gk in appendGroups) {
    // A new vessel takes the first spare pre-generated UUID row; with none left it
    // appends below the last row with a fresh UUID.
    var slot = spare.length ? spare.shift() : null;
    var newRow = [];
    for (var c2 = 0; c2 < header.length; c2++) {
      var h = String(header[c2]).trim();
      newRow.push(appendGroups[gk].hasOwnProperty(h) ? appendGroups[gk][h] : "");
    }
    newRow[ridCol] = slot ? slot.uuid : Utilities.getUuid();
    var preview = [];
    for (var h2 in appendGroups[gk]) preview.push(h2 + "='" + appendGroups[gk][h2] + "'");
    log.push((DRY_RUN ? "would " : "") + (slot ? "fill spare row " + slot.row : "append a row") +
             " [" + gk + "] UUID " + newRow[ridCol] + ": " + preview.join(", "));
    if (!DRY_RUN) {
      // Plain text first, so "2026" / "1/2" / leading zeros are not coerced (parity with push.py).
      var target = backend.getRange(slot ? slot.row : backend.getLastRow() + 1, 1, 1, newRow.length);
      target.setNumberFormat("@");
      target.setValues([newRow]);
    }
    appends++;
  }

  log.unshift("=== apply_patch " + (DRY_RUN ? "(DRY RUN — nothing written)" : "(WROTE CHANGES)") +
              " — " + sets + " cell(s), " + appends + " new row(s), " + skips + " skipped ===");
  Logger.log(log.join("\n"));
  SpreadsheetApp.getActiveSpreadsheet().toast(
    sets + " cells, " + appends + " rows" + (DRY_RUN ? " (dry run)" : " written") + ", " + skips + " skipped",
    "apply_patch", 8);
}

// Find the header row: the first row mentioning both 'shipowner' and 'shipbuilder'.
function findHeaderRow_(grid) {
  for (var r = 0; r < Math.min(grid.length, 5); r++) {
    var joined = grid[r].join(" ").toLowerCase();
    if (joined.indexOf("shipowner") >= 0 && joined.indexOf("shipbuilder") >= 0) return r;
  }
  return -1;
}
