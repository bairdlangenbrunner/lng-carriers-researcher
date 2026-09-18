/* Review app front end. Vanilla JS, no modules, no build step (phase 2 inlines this file
   into an Apps Script HtmlService page). All I/O goes through Store. */
(function () {
  "use strict";

  // ---- Store adapter (phase 1: local HTTP; phase 2 swaps in google.script.run) ----
  var Store = {
    _json: function (r) {
      return r.json().then(function (body) {
        if (!r.ok) throw new Error(body && body.error ? body.error : "HTTP " + r.status);
        return body;
      });
    },
    load: function () { return fetch("/api/data", {cache: "no-store"}).then(Store._json); },
    whoami: function () {
      return fetch("/api/whoami").then(Store._json).then(function (b) { return b.reviewer; });
    },
    decide: function (records) {
      return fetch("/api/decide", {method: "POST", headers: {"Content-Type": "application/json"},
                                   body: JSON.stringify(records)}).then(Store._json)
        .then(function (b) { return b.saved; });
    }
  };
  window.Store = Store;

  // ---- state ----
  var D = null;             // the dataset (review_data + current decisions)
  var ME = "";
  var S = {
    visible: [],            // vessel indexes passing the filter
    vessel: -1,             // index into D.vessels
    line: null,             // selected proposal key
    session: [],            // records saved this session
    undo: []                // per action: the prior state of the lines it changed
  };
  var $ = function (id) { return document.getElementById(id); };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    for (var k in (attrs || {})) e.setAttribute(k, attrs[k]);
    if (html != null) e.innerHTML = html;
    return e;
  }
  function batchOf(dir) {
    for (var i = 0; i < D.batches.length; i++) if (D.batches[i].dir === dir) return D.batches[i];
    return {label: dir, apply_order: 0};
  }
  function has(p, flag) { return p.flags.indexOf(flag) >= 0; }
  function rowLabel(v) { return v.new ? "new row" : (v.live_row == null ? "row gone" : "row " + v.live_row); }

  // ---- theme ----
  function initTheme() {
    try {
      var t = localStorage.getItem("review-theme");
      if (t) document.documentElement.setAttribute("data-theme", t);
    } catch (e) { /* storage blocked: follow the system theme */ }
    $("theme").onclick = function () {
      var cur = document.documentElement.getAttribute("data-theme") ||
        (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      var next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("review-theme", next); } catch (e) { /* ignore */ }
    };
  }

  // ---- filters ----
  var F = ["decision", "batch", "column", "confidence", "kind", "flag", "builder", "owner"];
  function fillSelect(id, values, labels) {
    var s = $(id);
    values.forEach(function (v, i) {
      var o = el("option", {value: v});
      o.textContent = labels ? labels[i] : v;
      s.appendChild(o);
    });
  }
  function uniq(arr) {
    return arr.filter(function (x, i) { return x && arr.indexOf(x) === i; }).sort(function (a, b) {
      return a.toLowerCase() < b.toLowerCase() ? -1 : 1;
    });
  }
  function initFilters() {
    var batches = D.batches.slice().sort(function (a, b) { return a.apply_order - b.apply_order; });
    fillSelect("f-batch", batches.map(function (b) { return b.dir; }),
               batches.map(function (b) { return b.label + (b.applied ? " (applied)" : ""); }));
    var cols = [], seen = {};
    Object.keys(D.proposals).forEach(function (k) {
      var c = D.proposals[k].column;
      if (!seen[c]) { seen[c] = 1; cols.push(c); }
    });
    cols.sort(function (a, b) {
      var ia = D.header.indexOf(a), ib = D.header.indexOf(b);
      return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib);
    });
    fillSelect("f-column", cols);
    fillSelect("f-builder", uniq(D.vessels.map(function (v) { return v.shipbuilder; })));
    fillSelect("f-owner", uniq(D.vessels.map(function (v) { return v.shipowner; })));
    F.forEach(function (f) { $("f-" + f).onchange = refilter; });
    $("f-mine").onchange = refilter;
    $("f-text").oninput = refilter;
    $("f-reset").onclick = function () {
      F.forEach(function (f) { $("f-" + f).value = ""; });
      $("f-decision").value = "hold";
      $("f-mine").checked = false;
      $("f-text").value = "";
      refilter();
    };
  }
  function filterState() {
    var st = {};
    F.forEach(function (f) { st[f] = $("f-" + f).value; });
    st.mine = $("f-mine").checked;
    st.text = $("f-text").value.trim().toLowerCase();
    return st;
  }
  function filterDescription(st) {
    st = st || filterState();
    var parts = [];
    if (st.batch) parts.push(batchOf(st.batch).label);
    if (st.column) parts.push(st.column);
    if (st.confidence) parts.push(st.confidence);
    if (st.decision) parts.push("decision " + st.decision);
    if (st.kind) parts.push("kind " + st.kind);
    if (st.flag) parts.push("flag " + st.flag);
    if (st.builder) parts.push(st.builder);
    if (st.owner) parts.push(st.owner);
    if (st.mine) parts.push("changed by me");
    if (st.text) parts.push('"' + st.text + '"');
    return parts.join(" · ") || "everything";
  }
  function vesselMatchesText(v, t) {
    if (!t) return true;
    var hay = [v.name, v.imo, v.live_row == null ? "" : String(v.live_row), v.hull].join(" ").toLowerCase();
    return hay.indexOf(t) >= 0 || (/^\d+$/.test(t) && String(v.live_row) === t);
  }
  function lineMatches(p, v, st) {
    if (st.decision && p.decision !== st.decision) return false;
    if (st.batch && p.batch !== st.batch) return false;
    if (st.column && p.column !== st.column) return false;
    if (st.confidence && p.confidence !== st.confidence) return false;
    if (st.kind && p.kind !== st.kind) return false;
    if (st.flag && !has(p, st.flag)) return false;
    if (st.builder && v.shipbuilder !== st.builder) return false;
    if (st.owner && v.shipowner !== st.owner) return false;
    if (st.mine && !(p.last && p.last.reviewer === ME)) return false;
    return vesselMatchesText(v, st.text);
  }
  function matchingKeys(st) {
    st = st || filterState();
    var out = [];
    D.vessels.forEach(function (v) {
      v.proposals.forEach(function (k) { if (lineMatches(D.proposals[k], v, st)) out.push(k); });
    });
    return out;
  }

  // ---- queue ----
  // keepCurrent: after a save, stay on the vessel even if it no longer matches (J moves on)
  function refilter(keepCurrent) {
    keepCurrent = keepCurrent === true;
    var st = filterState();
    var keep = D.vessels[S.vessel];
    S.visible = [];
    var nLines = 0;
    D.vessels.forEach(function (v, i) {
      var n = 0;
      v.proposals.forEach(function (k) { if (lineMatches(D.proposals[k], v, st)) n++; });
      v._match = n;
      nLines += n;
      if (n) S.visible.push(i);
    });
    $("count").textContent = nLines + " lines on " + S.visible.length + " vessels match";
    if (S.visible.indexOf(S.vessel) < 0 && !(keepCurrent && S.vessel >= 0))
      S.vessel = S.visible.length ? S.visible[0] : -1;
    renderVessels();
    if (keep !== D.vessels[S.vessel]) S.line = null;
    renderCard();
    renderProgress();
  }
  function renderProgress() {
    var holds = 0, total = 0;
    Object.keys(D.proposals).forEach(function (k) {
      total++;
      if (D.proposals[k].decision === "hold") holds++;
    });
    $("progress-bar").style.width = total ? (100 * (total - holds) / total) + "%" : "0";
    $("progress-text").textContent = holds + " holds remaining · " + S.session.length + " decided this session";
  }
  function holdsOf(v) {
    return v.proposals.filter(function (k) { return D.proposals[k].decision === "hold"; }).length;
  }
  function renderVessels() {
    var ol = $("vessels");
    ol.innerHTML = "";
    S.visible.forEach(function (i) {
      var v = D.vessels[i];
      var li = el("li", {"data-i": i});
      if (i === S.vessel) li.className = "sel";
      li.innerHTML = '<div class="vname">' + esc(v.name || "(no name)") + "</div>" +
        '<div class="vmeta"><span>' + esc(rowLabel(v)) + "</span><span>" + esc(v.shipbuilder) +
        "</span><span>" + esc(v.shipowner) + '</span><span class="n" title="matching / holds">' +
        v._match + " · " + holdsOf(v) + " held</span></div>";
      li.onclick = function () { selectVessel(i); };
      ol.appendChild(li);
    });
  }
  function selectVessel(i, lineKey) {
    S.vessel = i;
    S.line = lineKey || null;
    renderVessels();
    renderCard();
    var sel = $("vessels").querySelector("li.sel");
    if (sel) sel.scrollIntoView({block: "nearest"});
  }

  // Linked groups within one vessel: union of each line's links, emitted at first member.
  function groups(v) {
    var inV = {}, parent = {};
    v.proposals.forEach(function (k) { inV[k] = 1; parent[k] = k; });
    function find(k) { while (parent[k] !== k) k = parent[k] = parent[parent[k]]; return k; }
    v.proposals.forEach(function (k) {
      D.proposals[k].links.forEach(function (o) { if (inV[o]) parent[find(o)] = find(k); });
    });
    var byRoot = {}, order = [];
    v.proposals.forEach(function (k) {
      var r = find(k);
      if (!byRoot[r]) { byRoot[r] = []; order.push(r); }
      byRoot[r].push(k);
    });
    return order.map(function (r) { return byRoot[r]; });
  }
  function cardOrder(v) {
    var out = [];
    groups(v).forEach(function (g) { out = out.concat(g); });
    return out;
  }

  // Token diff for long text: "; "-separated lists (Other names) or words.
  function diff(a, b) {
    var sep = (a.indexOf("; ") >= 0 || b.indexOf("; ") >= 0) ? "; " : " ";
    var A = a ? a.split(sep) : [], B = b ? b.split(sep) : [];
    if (A.length * B.length > 250000) return {a: esc(a), b: esc(b)};
    var m = A.length, n = B.length, L = [], i, j;
    for (i = 0; i <= m; i++) { L.push(new Array(n + 1).fill(0)); }
    for (i = m - 1; i >= 0; i--) for (j = n - 1; j >= 0; j--)
      L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    var oa = [], ob = [];
    i = 0; j = 0;
    while (i < m && j < n) {
      if (A[i] === B[j]) { oa.push(esc(A[i])); ob.push(esc(B[j])); i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) { oa.push("<del>" + esc(A[i]) + "</del>"); i++; }
      else { ob.push("<ins>" + esc(B[j]) + "</ins>"); j++; }
    }
    for (; i < m; i++) oa.push("<del>" + esc(A[i]) + "</del>");
    for (; j < n; j++) ob.push("<ins>" + esc(B[j]) + "</ins>");
    return {a: oa.join(esc(sep)), b: ob.join(esc(sep))};
  }

  var FLAG_TEXT = {
    preserve_ref: "cosmetic — value rewritten, [ref] kept",
    append_ref: "appends to the cell",
    ref_only: "ref only",
    igu_pdf_only: "refs = IGU PDF only",
    strict_pair: "decide with its Name / Other names partner",
    applied: "already applied — changing it does not unapply it"
  };
  function verdictHtml(v) {
    if (!v) return '<span class="verdict">—</span>';
    var cls = /^(PASS|OK|ok|200)/.test(v) ? "pass" : (/^(FAIL|dead|banned)/i.test(v) ? "fail" : "");
    return '<span class="verdict ' + cls + '">' + esc(v) + "</span>";
  }
  function pairMismatch(p) {
    return p.links.some(function (o) {
      var q = D.proposals[o];
      return q && q.column !== p.column && q.decision !== p.decision;
    });
  }

  function lineHtml(k, p) {
    var b = batchOf(p.batch);
    var chips = ['<span class="chip ' + esc(p.confidence) + '">' + esc(p.confidence || "?") + "</span>"];
    if (p.derivable) chips.push('<span class="chip">derivable</span>');
    p.flags.forEach(function (f) {
      if (FLAG_TEXT[f]) chips.push('<span class="chip' + (f === "applied" ? " warn" : "") + '">' + esc(FLAG_TEXT[f]) + "</span>");
      else if (f.indexOf("verdict:") === 0) chips.push('<span class="chip">gate ' + esc(f.slice(8)) + "</span>");
    });
    if (has(p, "overlaps_batch")) chips.push('<span class="chip warn">same cell in another batch — the later batch wins on apply</span>');
    if (pairMismatch(p)) chips.push('<span class="chip warn">linked pair in different states</span>');

    var h = '<div class="row1"><span class="col">' +
      esc(p.column || "new row · cluster " + p.cluster_id) + "</span>" + chips.join(" ") +
      '<span class="batch">' + esc(b.label) + "</span>" +
      '<span class="state st-' + esc(p.decision) + '">' + esc(p.decision) +
      (p.last ? " · " + esc(p.last.reviewer) : "") + "</span></div>";

    if (p.kind === "new_row") {
      var rd = p.row_data || {};
      h += '<div class="note">' + esc(p.cluster_label) + "</div><table class=\"rowdata\">";
      D.header.concat(Object.keys(rd).filter(function (c) { return D.header.indexOf(c) < 0; }))
        .forEach(function (c) {
          if (rd[c] == null || rd[c] === "") return;
          var val = /\[ref\]$/.test(c)
            ? String(rd[c]).split(/,\s+/).map(function (u) {
                return /^https?:/.test(u) ? '<a href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(u) + "</a>" : esc(u);
              }).join("<br>")
            : esc(rd[c]);
          h += "<tr><td>" + esc(c) + "</td><td>" + val + "</td></tr>";
        });
      h += "</table>";
    } else if (p.kind === "ref" || has(p, "ref_only")) {
      // the value is untouched; the line adds the refs listed below
      h += '<div class="change"><span class="k">value</span><span class="v">' +
        (esc(p.cited_value || p.current) || '<span class="verdict">(blank)</span>') + " (unchanged)</span>" +
        '<span class="k">adds</span><span class="v">' + p.refs.length + " ref" + (p.refs.length === 1 ? "" : "s") +
        " to " + esc(p.ref_column || p.column) + "</span></div>";
    } else {
      var d = (p.current.length > 60 || p.proposed.length > 60) ? diff(p.current, p.proposed)
        : {a: esc(p.current), b: esc(p.proposed)};
      h += '<div class="change">';
      if (p.kind === "ref" && p.cited_value) h += '<span class="k">cites</span><span class="v">' + esc(p.cited_value) + "</span>";
      h += '<span class="k">current</span><span class="v">' + (d.a || '<span class="verdict">(blank)</span>') + "</span>" +
        '<span class="k">proposed</span><span class="v">' + (d.b || '<span class="verdict">(blank)</span>') + "</span>";
      if (p.suggestion) h += '<span class="k">suggested</span><span class="v st-suggest">' + esc(p.suggestion.value) +
        " (" + esc(p.suggestion.kind) + ")</span>";
      h += "</div>";
    }
    if (p.refs.length) {
      h += '<ul class="refs">' + p.refs.map(function (r) {
        return '<li><a href="' + esc(r.url) + '" target="_blank" rel="noopener">' + esc(r.url) + "</a> " + verdictHtml(r.verdict) + "</li>";
      }).join("") + "</ul>";
    }
    if (p.current_refs.length && p.kind !== "new_row")
      h += '<div class="note">current ' + esc(p.ref_column || "[ref]") + ": " + p.current_refs.map(function (u) {
        return '<a href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(u) + "</a>";
      }).join(", ") + "</div>";
    if (p.note) h += '<div class="note">' + esc(p.note) + "</div>";
    if (p.suggestion && p.suggestion.note) h += '<div class="note">suggestion note: ' + esc(p.suggestion.note) + "</div>";
    h += controlsHtml(k, p);
    return h;
  }
  var CONTROLS = [["accept", "a"], ["hold", "h"], ["reject", "r"]];
  function controlsHtml(k, p) {
    return '<div class="controls">' + CONTROLS.map(function (c) {
      return '<button type="button" class="b-' + c[0] + '" data-decide="' + c[0] + '" aria-pressed="' +
        (p.decision === c[0]) + '" title="' + c[0] + " (" + c[1] + ')">' + c[0] + "</button>";
    }).join("") + '<span class="saving" id="saving-' + esc(k) + '"></span></div>';
  }

  // ---- deciding ----
  var askPairs = true;   // "don't ask again" for ordinary pairs; never for Name <-> Other names
  function partnersOf(k) {
    var p = D.proposals[k];
    return p.links.filter(function (o) { return D.proposals[o] && D.proposals[o].column !== p.column; });
  }
  function isStrict(k, o) {
    var a = D.proposals[k].column, b = D.proposals[o].column;
    return a !== b && (a === "Name" || a === "Other names") && (b === "Name" || b === "Other names");
  }
  function lineName(k) {
    var p = D.proposals[k];
    return p.column + " (" + batchOf(p.batch).label + ")";
  }
  function applyRecord(rec) {
    var p = D.proposals[rec.key];
    p.decision = rec.decision;
    p.last = rec;
    p.suggestion = rec.decision === "suggest"
      ? {value: rec.suggested_value, kind: rec.suggest_kind, note: rec.note} : null;
  }
  function snapshotOf(keys) {
    return keys.map(function (k) {
      var p = D.proposals[k];
      return {key: k, decision: p.decision, suggestion: p.suggestion};
    });
  }
  function setSaving(keys, text, failed) {
    keys.forEach(function (k) {
      var s = document.getElementById("saving-" + k), line = document.getElementById("line-" + k);
      if (s) { s.textContent = text; s.className = failed ? "err" : "saving"; }
      if (line) line.classList.toggle("failed", !!failed);
    });
  }
  // Save records; the UI changes only after the server confirms (never optimistic-only).
  function save(records, undoable) {
    var keys = records.map(function (r) { return r.key; });
    var before = snapshotOf(keys);
    setSaving(keys, "Saving…");
    return Store.decide(records).then(function (saved) {
      saved.forEach(applyRecord);
      S.session = S.session.concat(saved);
      if (undoable) S.undo.push(before);
      banner("");
      refreshAfterSave();
      return saved;
    }).catch(function (e) {
      setSaving(keys, "Not saved: " + e.message, true);
      banner("Save failed — nothing was recorded for " + keys.length + " line(s): " + e.message);
      throw e;
    });
  }
  function refreshAfterSave() {
    var keepLine = S.line;
    refilter(true);
    if (keepLine && document.getElementById("line-" + keepLine)) setLine(keepLine, true);
  }

  function decideLine(k, decision, opts) {
    opts = opts || {};
    var p = D.proposals[k];
    var keys = [k];
    var partners = partnersOf(k).filter(function (o) { return D.proposals[o].decision !== decision; });
    var chain = Promise.resolve(true);
    if (partners.length) {
      var strict = partners.some(function (o) { return isStrict(k, o); });
      if (strict || askPairs) {
        chain = dialog("<h3>Linked " + (partners.length > 1 ? "lines" : "line") + "</h3><p>You are setting <b>" +
          esc(lineName(k)) + "</b> to <b>" + esc(decision) + "</b>. Same for " +
          partners.map(function (o) { return "<b>" + esc(lineName(o)) + "</b> (now " + esc(D.proposals[o].decision) + ")"; })
            .join(", ") + "?</p>" +
          (strict ? "<p>Name and Other names are decided together (RF §4.16).</p>"
                  : '<label><input type="checkbox" id="dlg-noask"> don\'t ask again this session</label>'),
          strict ? [["Cancel", null], ["Both", "both"]] : [["Cancel", null], ["Only this line", "one"], ["Both", "both"]]
        ).then(function (ans) {
          var cb = document.getElementById("dlg-noask");
          if (cb && cb.checked && ans) askPairs = false;
          if (ans === "both") keys = keys.concat(partners);
          return !!ans;
        });
      }
    }
    return chain.then(function (go) {
      if (!go) return null;
      var applied = keys.filter(function (x) { return has(D.proposals[x], "applied") && D.proposals[x].decision !== decision; });
      if (!applied.length) return true;
      return dialog("<h3>Already applied</h3><p>" + applied.length + " of these lines belong to a batch that is " +
        "already in the backend. Changing the decision records it, but does <b>not</b> unapply anything — " +
        "a change to the sheet needs its own fix batch.</p>", [["Cancel", null], ["Record it", true]]);
    }).then(function (go) {
      if (!go) return null;
      var recs = keys.map(function (x, i) {
        return {key: x, decision: decision, via: i === 0 ? (opts.via || "single") : "linked"};
      });
      return save(recs, true).then(function (saved) {
        if (opts.advance && S.line === k) stepLine(1);
        return saved;
      });
    }).catch(function () { return null; });
  }

  function undo() {
    var prev = S.undo.pop();
    if (!prev) return banner("Nothing to undo.");
    var recs = prev.map(function (s) {
      var r = {key: s.key, decision: s.decision, via: "undo"};
      if (s.decision === "suggest" && s.suggestion) {
        r.suggested_value = s.suggestion.value;
        r.suggest_kind = s.suggestion.kind;
        r.note = s.suggestion.note;
      }
      return r;
    });
    save(recs, false).then(function () {
      var v = D.vessels.findIndex(function (x) { return x.proposals.indexOf(recs[0].key) >= 0; });
      if (v >= 0 && v !== S.vessel) selectVessel(v, recs[0].key);
      else setLine(recs[0].key);
    }).catch(function () { S.undo.push(prev); });
  }

  function onCardClick(e) {
    var b = e.target.closest("button[data-decide]");
    if (!b) return;
    var line = b.closest(".line");
    setLine(line.getAttribute("data-key"), true);
    decideLine(line.getAttribute("data-key"), b.getAttribute("data-decide"));
  }

  function renderCard() {
    var card = $("card");
    if (S.vessel < 0) {
      card.innerHTML = '<div class="empty">Nothing matches the filters.</div>';
      return;
    }
    var v = D.vessels[S.vessel], st = filterState();
    var h = "<h2>" + esc(v.name || "(no name)") + "</h2><div class=\"ctx\">" +
      ["<b>" + esc(rowLabel(v)) + "</b>", v.imo && "IMO " + esc(v.imo), v.status && esc(v.status),
       v.shipbuilder && esc(v.shipbuilder), v.hull && "hull " + esc(v.hull), v.shipowner && esc(v.shipowner),
       v.delivery_year && "delivery " + esc(v.delivery_year),
       !v.new && !v.in_backend && '<span class="chip warn">row no longer in backend</span>']
        .filter(Boolean).map(function (x) { return "<span>" + x + "</span>"; }).join("") + "</div>";
    card.innerHTML = h;
    groups(v).forEach(function (g) {
      var box = el("div", {"class": "group" + (g.length > 1 ? " linked" : "")});
      if (g.length > 1) box.appendChild(el("div", {"class": "grouphead"}, "linked · " +
        esc(uniq(g.map(function (k) { return D.proposals[k].column; })).join(" ↔ "))));
      g.forEach(function (k) {
        var p = D.proposals[k];
        var line = el("div", {"class": "line", "data-key": k, id: "line-" + k});
        if (!lineMatches(p, v, st)) line.className += " off";
        if (k === S.line) line.className += " cur";
        line.innerHTML = lineHtml(k, p);
        line.addEventListener("click", function (e) {
          if (e.target.closest("a,button,input,textarea,select")) return;
          setLine(k);
        });
        box.appendChild(line);
      });
      card.appendChild(box);
    });
    if (!S.line) {
      var first = cardOrder(v).filter(function (k) { return lineMatches(D.proposals[k], v, st); })[0];
      if (first) setLine(first, true);
    }
  }
  function setLine(k, noScroll) {
    var prev = S.line && document.getElementById("line-" + S.line);
    if (prev) prev.classList.remove("cur");
    S.line = k;
    var cur = document.getElementById("line-" + k);
    if (cur) {
      cur.classList.add("cur");
      if (!noScroll) cur.scrollIntoView({block: "nearest"});
    }
  }

  // ---- keyboard navigation ----
  function stepLine(dir) {
    if (S.vessel < 0) return;
    var st = filterState();
    var v = D.vessels[S.vessel];
    var keys = cardOrder(v).filter(function (k) { return lineMatches(D.proposals[k], v, st) || k === S.line; });
    var i = keys.indexOf(S.line) + dir;
    if (i >= 0 && i < keys.length) return setLine(keys[i]);
    stepVessel(dir, dir < 0);
  }
  function stepVessel(dir, toLast) {
    // the current vessel may have dropped out of the filter; step from its list position
    var next = dir > 0
      ? S.visible.filter(function (i) { return i > S.vessel; })[0]
      : S.visible.filter(function (i) { return i < S.vessel; }).pop();
    if (next == null) return;
    selectVessel(next);
    if (toLast) {
      var v = D.vessels[S.vessel], st = filterState();
      var keys = cardOrder(v).filter(function (k) { return lineMatches(D.proposals[k], v, st); });
      if (keys.length) setLine(keys[keys.length - 1]);
    }
  }
  function openFirstRef() {
    var p = S.line && D.proposals[S.line];
    var url = p && (p.refs[0] ? p.refs[0].url : p.current_refs[0]);
    if (url) window.open(url, "_blank", "noopener");
  }
  var KEYS = {
    j: function () { stepLine(1); }, k: function () { stepLine(-1); },
    J: function () { stepVessel(1); }, K: function () { stepVessel(-1); },
    o: openFirstRef,
    a: function () { if (S.line) decideLine(S.line, "accept", {advance: true}); },
    h: function () { if (S.line) decideLine(S.line, "hold", {advance: true}); },
    r: function () { if (S.line) decideLine(S.line, "reject", {advance: true}); },
    u: undo,
    "/": function (e) { e.preventDefault(); $("f-text").focus(); $("f-text").select(); },
    "?": showHelp
  };
  var HELP = [["j / k", "next / previous line"], ["J / K", "next / previous vessel"],
              ["a / h / r", "accept / hold / reject the line (saved at once)"],
              ["u", "undo the last action (adds a record; the log is never rewritten)"],
              ["o", "open the line's first ref"], ["/", "search"], ["?", "this help"]];
  function showHelp() {
    dialog("<h3>Keyboard</h3><table>" + HELP.map(function (r) {
      return "<tr><td><kbd>" + r[0] + "</kbd></td><td>" + r[1] + "</td></tr>";
    }).join("") + "</table>", [["Close", null]]);
  }
  function onKey(e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var t = e.target;
    if ($("dialog").open) return;
    if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) {
      if (e.key === "Escape") t.blur();
      return;
    }
    var f = KEYS[e.key];
    if (f && !$("tab-queue").hidden) f(e);
    else if (e.key === "?") showHelp();
  }

  // ---- dialog helper: resolves to the chosen button's value ----
  function dialog(html, buttons) {
    var dlg = $("dialog");
    dlg.innerHTML = html + '<div class="actions"></div>';
    return new Promise(function (resolve) {
      var box = dlg.querySelector(".actions");
      buttons.forEach(function (b, i) {
        var btn = el("button", {type: "button"}, esc(b[0]));
        btn.onclick = function () { dlg.close(); resolve(b[1]); };
        box.appendChild(btn);
        if (i === buttons.length - 1) setTimeout(function () { btn.focus(); }, 0);
      });
      dlg.oncancel = function () { resolve(null); };
      dlg.showModal();
    });
  }

  // ---- tabs ----
  function initTabs() {
    Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (t) {
      t.onclick = function () { showTab(t.getAttribute("data-tab")); };
    });
  }
  function showTab(name) {
    Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (t) {
      t.classList.toggle("active", t.getAttribute("data-tab") === name);
    });
    ["queue", "items", "summary"].forEach(function (n) { $("tab-" + n).hidden = n !== name; });
  }

  function banner(msg) {
    var b = $("banner");
    b.textContent = msg;
    b.hidden = !msg;
  }

  // ---- boot ----
  // Exposed for the later milestones and for debugging in the console.
  window.ReviewApp = {
    get data() { return D; }, state: S, refilter: refilter, renderCard: renderCard,
    matchingKeys: matchingKeys, filterDescription: filterDescription, dialog: dialog, banner: banner
  };

  initTheme();
  initTabs();
  document.addEventListener("keydown", onKey);
  $("card").addEventListener("click", onCardClick);
  Promise.all([Store.load(), Store.whoami()]).then(function (r) {
    D = r[0];
    ME = r[1];
    $("whoami").textContent = ME;
    $("built").textContent = "built " + D.built.replace("T", " ").slice(0, 16) +
      " · backend pulled " + D.backend_pulled.replace("T", " ").slice(0, 16);
    initFilters();
    refilter();
  }).catch(function (e) { banner("Could not load the review data: " + e.message); });
})();
