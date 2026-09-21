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
    },
    refresh: function () {       // re-pull the backend, rebuild, settle what the backend settles
      return fetch("/api/refresh", {method: "POST", headers: {"Content-Type": "application/json"},
                                    body: "{}"}).then(Store._json);
    },
    pushPlan: function (batch) { // re-pull, then every cell the accepted lines would change
      return fetch("/api/push/plan", {method: "POST", headers: {"Content-Type": "application/json"},
                                      body: JSON.stringify({batch: batch || null})}).then(Store._json);
    },
    push: function (token, includeApplied, batch) {   // the one backend write; 409 = plan went stale
      return fetch("/api/push", {method: "POST", headers: {"Content-Type": "application/json"},
                                 body: JSON.stringify({token: token, include_applied: includeApplied,
                                                       batch: batch || null})})
        .then(Store._json);
    },
    item: function (records) {   // Items tab: status / note / a conflict's call
      return fetch("/api/item", {method: "POST", headers: {"Content-Type": "application/json"},
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
    itemSession: [],        // item records saved this session
    undo: [],               // per action: the prior state of the lines it changed
    open: {}                // proposal keys whose "details" are open (kept across re-renders)
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
    $("f-more").onclick = function () { toggleMore(); };
    $("active-filters").onclick = function (e) {
      var b = e.target.closest("button[data-clear]");
      if (!b) return;
      var id = b.getAttribute("data-clear");
      if (id === "mine") $("f-mine").checked = false; else $("f-" + id).value = "";
      refilter();
    };
    $("f-reset").onclick = function () {
      F.forEach(function (f) { $("f-" + f).value = ""; });
      $("f-decision").value = "hold";
      $("f-mine").checked = false;
      $("f-text").value = "";
      refilter();
    };
  }
  // Decision, Batch and Search stay in view; the rest sit behind "More filters". A filter that
  // is set is always visible as a removable chip, so a hidden control never filters silently.
  var MORE = ["column", "confidence", "kind", "flag", "builder", "owner"];
  function toggleMore(open) {
    var box = $("more-filters");
    box.hidden = open == null ? !box.hidden : !open;
    $("f-more").setAttribute("aria-expanded", String(!box.hidden));
    renderActiveFilters();
  }
  function renderActiveFilters() {
    var st = filterState(), chips = [];
    function chip(id, text) {
      chips.push('<span class="chip on">' + esc(text) + ' <button type="button" data-clear="' + id +
        '" title="clear this filter" aria-label="clear ' + esc(text) + '">×</button></span>');
    }
    MORE.forEach(function (f) {
      if (!st[f]) return;
      var sel = $("f-" + f), o = sel.options[sel.selectedIndex];
      chip(f, sel.parentNode.firstChild.textContent.trim().toLowerCase() + ": " + (o ? o.textContent : st[f]));
    });
    if (st.mine) chip("mine", "changed by me");
    $("active-filters").innerHTML = chips.join(" ");
    $("active-filters").hidden = !chips.length || !$("more-filters").hidden;   // open: the controls say it
    var n = chips.length;
    $("f-more").textContent = ($("more-filters").hidden ? "More filters" : "Fewer filters") + (n ? " (" + n + ")" : "");
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
    renderActiveFilters();
    $("count").textContent = nLines + " lines on " + S.visible.length + " vessels match";
    renderBulk(nLines);
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
        '<div class="vmeta"><span>' + esc(rowLabel(v)) + '</span><span class="who2" title="' +
        esc([v.shipbuilder, v.shipowner].filter(Boolean).join(" · ")) + '">' +
        esc([v.shipbuilder, v.shipowner].filter(Boolean).join(" · ")) + "</span>" +
        (holdsOf(v) ? '<span class="n todo" title="lines on hold / lines matching the filter">' + holdsOf(v) + " to decide</span>"
                    : '<span class="n" title="nothing on hold">' + v._match + " · done</span>") + "</div>";
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

  // Chips are one or two words; the sentence lives in the tooltip. Red is for "act on this".
  var FLAG_TEXT = {
    preserve_ref: ["cosmetic", "the value is rewritten, the cell's [ref] is kept"],
    append_ref: ["appends", "added to what the cell already holds, nothing is replaced"],
    ref_only: ["ref only", "adds refs; the value is untouched"],
    igu_pdf_only: ["only source: IGU", "the IGU report PDF is the sole ref (interim ruling 2026-09-17)"],
    in_backend: ["in the backend", "the pulled backend already holds this value and its refs"],
    value_in_backend: ["value in the backend", "the backend holds this value, but not every proposed ref"],
    applied: ["already applied", "this batch is in the backend — changing the decision does not unapply it"]
  };
  var CONF_TEXT = {G: "green — auto-accept grade", Y: "yellow — held for a decision", R: "red — weak support"};
  var STATUS_TEXT = {verified: "✓ verified", failed: "✗ failed the gate", read: "read by hand", unchecked: "not checked"};
  function verdictHtml(r) {
    var t = STATUS_TEXT[r.status] || r.reason;
    if (r.status === "failed" && r.reason) t += " — " + r.reason;
    return '<span class="verdict ' + esc(r.status) + '" title="' + esc(r.verdicts.join("\n")) + '">' + esc(t) + "</span>";
  }
  function sourceHtml(r) {
    return '<a href="' + esc(r.href) + '" target="_blank" rel="noopener" title="' + esc(r.url) + '">' + esc(r.label) + " ↗</a>" +
      (r.companion ? ' <a class="src-more" href="' + esc(r.companion) + '" target="_blank" rel="noopener" title="' +
        esc(r.companion) + ' — the unit record behind a page that renders blank">(data ↗)</a>' : "") + " " + verdictHtml(r);
  }
  function link(u) { return '<a href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(u) + "</a>"; }
  function blank() { return '<span class="blank">blank</span>'; }
  // the same cell proposed by another batch: quiet when the values agree, red when they do not
  function overlapChips(p) {
    return p.links.map(function (o) { return D.proposals[o]; }).filter(function (q) {
      return q && q.column === p.column && q.kind !== "ref" && p.kind !== "ref";
    }).map(function (q) {
      var n = "batch " + batchOf(q.batch).apply_order;
      return q.proposed === p.proposed
        ? '<span class="chip" title="' + esc(batchOf(q.batch).label) + ' proposes the same value">also in ' + esc(n) + "</span>"
        : '<span class="chip warn" title="' + esc(batchOf(q.batch).label) + " proposes “" + esc(q.proposed) +
          '” — the later batch wins on apply">' + esc(n) + " differs</span>";
    });
  }
  // only worth saying once a person has decided one side; defaults differ by confidence
  function pairMismatch(p) {
    return p.links.some(function (o) {
      var q = D.proposals[o];
      return q && q.column !== p.column && q.decision !== p.decision && (p.last || q.last);
    });
  }

  function lineHtml(k, p) {
    var b = batchOf(p.batch);
    var chips = ['<span class="chip ' + esc(p.confidence) + '" title="' + esc(CONF_TEXT[p.confidence] || "no confidence grade") +
                 '">' + esc(p.confidence || "?") + "</span>"];
    if (p.derivable) chips.push('<span class="chip" title="computed from other cells, not researched">derived</span>');
    p.flags.forEach(function (f) {
      if (FLAG_TEXT[f]) chips.push('<span class="chip' + (f === "applied" ? " warn" : "") + '" title="' +
        esc(FLAG_TEXT[f][1]) + '">' + esc(FLAG_TEXT[f][0]) + "</span>");
    });
    chips = chips.concat(overlapChips(p));
    if (pairMismatch(p)) chips.push('<span class="chip warn" title="its linked line has a different decision">pair split</span>');

    var h = '<div class="row1"><span class="col">' +
      esc(p.column || "new row · cluster " + p.cluster_id) + "</span>" + chips.join(" ") +
      '<span class="batch">' + "batch " + esc(b.label) + "</span></div>";

    if (p.kind === "new_row") {
      var rd = p.row_data || {};
      // sources are numbered once (the Sources list below); a [ref] cell cites them as [1][2]
      var num = {};
      p.sources.forEach(function (r, i) { num[r.url] = i + 1; if (r.companion) num[r.companion] = i + 1; });
      h += '<div class="note">' + esc(p.cluster_label) + "</div><table class=\"rowdata\">";
      D.header.concat(Object.keys(rd).filter(function (c) { return D.header.indexOf(c) < 0; }))
        .forEach(function (c) {
          if (rd[c] == null || rd[c] === "" || /\[ref\]$/.test(c)) return;
          var cites = String(rd[c + " [ref]"] || "").split(/,\s+/).filter(Boolean).map(function (u) {
            return num[u] ? '<a class="cite" href="' + esc(u) + '" target="_blank" rel="noopener" title="' + esc(u) +
              '">[' + num[u] + "]</a>" : (/^https?:/.test(u) ? link(u) : esc(u));
          }).join(" ");
          h += "<tr><td>" + esc(c) + "</td><td>" + esc(rd[c]) + (cites ? ' <span class="cites">' + cites + "</span>" : "") + "</td></tr>";
        });
      Object.keys(rd).forEach(function (c) {       // a [ref] with no value beside it: never hide it
        if (/\[ref\]$/.test(c) && rd[c] && !rd[c.replace(/ \[ref\]$/, "")])
          h += "<tr><td>" + esc(c) + "</td><td>" + esc(rd[c]) + "</td></tr>";
      });
      h += "</table>";
    } else if (p.kind === "ref" || has(p, "ref_only")) {
      // the value is untouched; the line adds the sources listed below
      h += '<div class="value">' + (esc(p.cited_value || p.current) || blank()) +
        ' <span class="was">— value unchanged; adds ' + p.refs.length + " ref" + (p.refs.length === 1 ? "" : "s") +
        " to " + esc(p.ref_column || p.column) + "</span></div>";
    } else if (p.current.length > 40 || p.proposed.length > 40) {
      var d = diff(p.current, p.proposed);
      h += '<div class="value long"><span class="was">now</span><span>' + (d.a || blank()) + "</span>" +
        '<span class="was">proposed</span><span>' + (d.b || blank()) + "</span></div>";
    } else {
      h += '<div class="value"><span class="was">' + (esc(p.current) || blank()) + '</span><span class="arrow">→</span>' +
        (esc(p.proposed) || blank()) + "</div>";
    }

    h += '<div class="facts">';
    if (p.suggestion) h += '<span class="k">Suggested</span><span class="v st-suggest">' + esc(p.suggestion.value) +
      " (" + esc(p.suggestion.kind) + ")" + (p.suggestion.note ? " — " + esc(p.suggestion.note) : "") + "</span>";
    // a reason that runs past a few lines is clamped, never cut: "more" shows the rest in place
    if (p.why) h += '<span class="k">Why</span><span class="v">' + (p.why.length > 360 && !S.open["why:" + k]
      ? '<span class="why-clamp">' + esc(p.why) + '</span><button type="button" class="more" data-why="' + esc(k) + '">more</button>'
      : esc(p.why)) + "</span>";
    var numbered = p.kind === "new_row";
    if (p.sources.length) h += '<span class="k">Source' + (p.sources.length > 1 ? "s" : "") + '</span><span class="v"><' +
      (numbered ? 'ol class="numbered"' : "ul") + ">" +
      p.sources.map(function (r) { return "<li>" + sourceHtml(r) + "</li>"; }).join("") + "</" + (numbered ? "ol" : "ul") + "></span>";
    h += "</div>";

    // everything else: nothing is hidden for good, it is one click away
    var more = p.detail.map(function (t) { return "<div>" + esc(t) + "</div>"; });
    if (p.current_refs.length && p.kind !== "new_row")
      more.push('<div><span class="k">' + (p.kind === "fill" && !has(p, "preserve_ref") && !has(p, "append_ref") && p.refs.length
        ? "replaces " : "current ") + esc(p.ref_column || "[ref]") + ":</span> " + p.current_refs.map(link).join(", ") + "</div>");
    if (p.refs.length) more.push('<div><span class="k">gate:</span> ' + p.sources.map(function (r) {
      return r.verdicts.map(esc).join("<br>"); }).join("<br>") + "</div>");
    if (more.length) h += "<details" + (S.open[k] ? " open" : "") + ' data-more><summary>details</summary>' + more.join("") + "</details>";
    h += controlsHtml(k, p);
    return h;
  }
  var CONTROLS = [["accept", "a"], ["hold", "h"], ["reject", "r"]];
  // a suggestion replaces a proposed cell value; a new row or a ref-only line has none
  function canSuggest(p) { return p.kind !== "new_row" && p.kind !== "ref" && !has(p, "ref_only"); }
  function controlsHtml(k, p) {
    return '<div class="controls">' + CONTROLS.map(function (c) {
      return '<button type="button" class="b-' + c[0] + '" data-decide="' + c[0] + '" title="' + c[0] + " (" + c[1] + ')" aria-pressed="' +
        (p.decision === c[0]) + '">' + c[0] + "</button>";
    }).join("") + '<button type="button" class="b-suggest" data-suggest aria-pressed="' + (p.decision === "suggest") +
      '"' + (canSuggest(p) ? ' title="suggest a different value (s)"'
                           : ' disabled title="nothing to suggest on a new row or a ref-only line"') +
      ">suggest…</button>" + (p.last ? '<span class="by">' + esc(p.decision) + " by " + esc(p.last.reviewer) + "</span>" : "") +
      '<span class="saving" id="saving-' + esc(k) + '"></span></div>';
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
    if (!$("tab-summary").hidden) renderSummary();
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

  // Suggest: the value as proposed is not wanted (reject in decisions.csv); the replacement
  // reaches the backend only through a fix batch that re-gates it (suggestions.py).
  function suggestLine(k) {
    var p = D.proposals[k];
    if (!canSuggest(p)) return banner("Nothing to suggest on a new row or a ref-only line.");
    var s0 = p.suggestion || {value: p.proposed, kind: "value", note: ""};
    var strict = partnersOf(k).filter(function (o) { return isStrict(k, o); });
    var h = "<h3>Suggest a value — " + esc(lineName(k)) + "</h3>" +
      '<p class="note">current: ' + (esc(p.current) || "(blank)") + "<br>proposed: " + (esc(p.proposed) || "(blank)") + "</p>" +
      '<label class="stack">suggested value<textarea id="sg-value" rows="3">' + esc(s0.value) + "</textarea></label>" +
      '<fieldset class="stack"><label><input type="radio" name="sg-kind" value="value"' + (s0.kind !== "cosmetic" ? " checked" : "") +
      "> value — a different fact; the original refs are re-gated against it</label>" +
      '<label><input type="radio" name="sg-kind" value="cosmetic"' + (s0.kind === "cosmetic" ? " checked" : "") +
      "> cosmetic — spelling, stylization, same fact; the cell's [ref] is kept</label></fieldset>" +
      '<label class="stack">note (required)<textarea id="sg-note" rows="2">' + esc(s0.note) + "</textarea></label>" +
      '<p class="err" id="sg-err"></p>' +
      "<p><b>Nothing is applied from here.</b> The line is recorded as <i>suggest</i> (reject in decisions.csv); " +
      "the suggestion becomes a fix batch (<code>review_app/suggestions.py</code>) and reaches the backend only " +
      "after it passes the §3.8c gate and its own review.</p>" +
      (strict.length ? "<p class=\"warn\">Linked: " + strict.map(function (o) {
        return esc(lineName(o)) + " is " + esc(D.proposals[o].decision); }).join(", ") +
        ". other_names.py re-derives the former name in the suggestion's fix batch — decide the partner here yourself.</p>" : "") +
      (has(p, "applied") ? '<p class="warn">This batch is already applied: recording a suggestion unapplies nothing.</p>' : "");
    var dlg = $("dialog");
    function attempt() {
      var v = $("sg-value").value, n = $("sg-note").value.trim();
      var kind = dlg.querySelector("input[name=sg-kind]:checked").value;
      if (!v.trim()) { $("sg-err").textContent = "A suggestion needs a value."; return false; }
      if (!n) { $("sg-err").textContent = "A suggestion needs a note."; return false; }
      if (v === p.proposed && kind === "value") { $("sg-err").textContent = "That is the proposed value — accept it instead."; return false; }
      return {key: k, decision: "suggest", suggested_value: v, suggest_kind: kind, note: n, via: "single"};
    }
    var shown = dialog(h, [["Cancel", null], ["Save suggestion", attempt]]);
    [].forEach.call(dlg.querySelectorAll("textarea, input"), function (f) {   // fresh nodes per dialog
      f.addEventListener("input", function () { $("sg-err").textContent = ""; });
    });
    return shown.then(function (rec) {
      if (!rec) return null;
      return save([rec], true);
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
    var w = e.target.closest("button[data-why]");
    if (w) { S.open["why:" + w.getAttribute("data-why")] = true; return renderCard(); }
    var sg = e.target.closest("button[data-suggest]");
    if (sg) {
      var l = sg.closest(".line");
      setLine(l.getAttribute("data-key"), true);
      return suggestLine(l.getAttribute("data-key"));
    }
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
      if (g.length > 1) {
        var cols = uniq(g.map(function (k) { return D.proposals[k].column; }));
        var strictG = g.some(function (k) { return has(D.proposals[k], "strict_pair"); });
        box.appendChild(el("div", {"class": "grouphead"}, cols.length > 1
          ? esc(cols.join(" ↔ ")) + (strictG ? " — decided together" : " — linked")
          : esc(cols[0]) + " — proposed by " + g.length + " batches"));
      }
      g.forEach(function (k) {
        var p = D.proposals[k];
        var line = el("div", {"class": "line d-" + p.decision, "data-key": k, id: "line-" + k});
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
    d: function () {
      var l = S.line && document.getElementById("line-" + S.line), m = l && l.querySelector("details[data-more]");
      if (m) m.open = !m.open;
    },
    a: function () { if (S.line) decideLine(S.line, "accept", {advance: true}); },
    h: function () { if (S.line) decideLine(S.line, "hold", {advance: true}); },
    r: function () { if (S.line) decideLine(S.line, "reject", {advance: true}); },
    s: function (e) { if (S.line) { e.preventDefault(); suggestLine(S.line); } },
    u: undo,
    "/": function (e) { e.preventDefault(); $("f-text").focus(); $("f-text").select(); },
    "?": showHelp
  };
  var HELP = [["j / k", "next / previous line"], ["J / K", "next / previous vessel"],
              ["a / h / r", "accept / hold / reject the line (saved at once)"],
              ["s", "suggest a different value (a form; applied only through a re-gated fix batch)"],
              ["u", "undo the last action (adds a record; the log is never rewritten)"],
              ["o", "open the line's first ref"], ["d", "show / hide the line's details"], ["/", "search"], ["?", "this help"]];
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
        btn.onclick = function () {
          var v = typeof b[1] === "function" ? b[1]() : b[1];
          if (v === false) return;          // validation failed: keep the dialog open
          dlg.close();
          resolve(v);
        };
        box.appendChild(btn);
        if (i === buttons.length - 1 && !dlg.querySelector("textarea,input")) setTimeout(function () { btn.focus(); }, 0);
      });
      dlg.oncancel = function () { resolve(null); };
      dlg.showModal();
      var field = dlg.querySelector("textarea,input[type=text]");
      if (field) field.focus();
    });
  }


  // ---- bulk: apply to all N filtered ----
  function renderBulk(n) {
    var slot = $("bulk-slot");
    if (!slot.firstChild) {
      slot.innerHTML = 'apply to all <b id="bulk-n"></b> filtered: ' + CONTROLS.map(function (c) {
        return '<button type="button" class="b-' + c[0] + '" data-bulk="' + c[0] + '">' + c[0] + "</button>";
      }).join(" ");
      slot.onclick = function (e) {
        var b = e.target.closest("button[data-bulk]");
        if (b) bulkDecide(b.getAttribute("data-bulk"));
      };
    }
    $("bulk-n").textContent = n;
    Array.prototype.forEach.call(slot.querySelectorAll("button"), function (b) { b.disabled = !n; });
  }
  function bulkDecide(decision) {
    var st = filterState(), desc = filterDescription(st);
    var keys = matchingKeys(st);
    var inSet = {};
    keys.forEach(function (k) { inSet[k] = 1; });
    var change = keys.filter(function (k) { return D.proposals[k].decision !== decision; });
    // bulk never crosses a linked pair silently: partners outside the filter are named
    var partners = [], strict = false;
    change.forEach(function (k) {
      partnersOf(k).forEach(function (o) {
        if (inSet[o] || partners.indexOf(o) >= 0 || D.proposals[o].decision === decision) return;
        partners.push(o);
        if (isStrict(k, o)) strict = true;
      });
    });
    if (!change.length) {
      return dialog("<h3>Nothing to change</h3><p>All " + keys.length + " filtered lines are already <b>" +
        esc(decision) + "</b>.</p>", [["Close", null]]);
    }
    var h = "<h3>" + esc(decision) + " " + change.length + " line" + (change.length === 1 ? "" : "s") +
      " — " + esc(desc) + "</h3><p>" + keys.length + " lines match the filter; " + change.length +
      " change to <b>" + esc(decision) + "</b>" +
      (keys.length > change.length ? " (" + (keys.length - change.length) + " already are)" : "") + ".</p>";
    var applied = function (list) {
      return list.filter(function (k) { return has(D.proposals[k], "applied"); }).length;
    };
    if (partners.length) {
      h += "<p>The filter catches only one half of " + partners.length + " linked pair" +
        (partners.length === 1 ? "" : "s") + ". Partners outside it: " + uniq(partners.map(function (o) {
          return D.proposals[o].column; })).map(esc).join(", ") + ".</p>";
      if (strict) h += "<p>Name and Other names are decided together (RF §4.16), so those partners are included.</p>";
    }
    var btns = [["Cancel", null]];
    if (partners.length && !strict) btns.push(["Only the filtered lines", "one"]);
    btns.push([partners.length ? "Include the partners" : esc(decision) + " " + change.length, "both"]);
    var nApplied = applied(change.concat(partners));
    if (nApplied) h += '<p class="warn">' + nApplied + " line(s) belong to an already-applied batch: the " +
      "decision is recorded, nothing is unapplied.</p>";
    return dialog(h, btns).then(function (ans) {
      if (!ans) return null;
      var recs = change.map(function (k) { return {key: k, decision: decision, via: "bulk:" + desc}; });
      if (ans === "both") recs = recs.concat(partners.map(function (o) {
        return {key: o, decision: decision, via: "linked"};
      }));
      return save(recs, true);
    }).catch(function () { return null; });
  }

  // ---- Items tab: conflicts, manual review, proposed bucket, duplicates, flags ----
  var ITEM_STATUSES = ["open", "resolved", "needs research"];
  var ITEM_TYPES = {conflict: "conflict", manual: "manual review", proposed_bucket: "proposed bucket",
                    duplicate: "possible duplicate", flag: "flag"};
  function vesselIndexForRow(r) {
    for (var i = 0; i < D.vessels.length; i++) if (D.vessels[i].live_row === r) return i;
    return -1;
  }
  function renderItems() {
    var box = $("tab-items");
    if (!box.firstChild) {
      box.innerHTML = '<form class="filters" id="item-filters" onsubmit="return false">' +
        '<label>Status <select id="i-status"><option value="">any</option></select></label>' +
        '<label>Type <select id="i-type"><option value="">any</option></select></label>' +
        '<label>Batch <select id="i-batch"><option value="">any</option></select></label>' +
        '<span id="i-count"></span></form><div id="item-list" class="summary"></div>';
      fillSelect("i-type", Object.keys(ITEM_TYPES), Object.keys(ITEM_TYPES).map(function (t) { return ITEM_TYPES[t]; }));
      fillSelect("i-status", ITEM_STATUSES);
      $("i-status").value = "open";            // like the queue's "hold": what is left to do
      var bs = uniq(D.items.map(function (it) { return it.batch; }));
      fillSelect("i-batch", bs, bs.map(function (b) { return batchOf(b).label; }));
      ["i-type", "i-status", "i-batch"].forEach(function (id) { $(id).onchange = renderItemList; });
      $("item-list").addEventListener("click", onItemClick);
      $("item-list").addEventListener("change", onItemNote);
    }
    renderItemList();
  }
  function itemVisible(it) {
    var t = $("i-type").value, stt = $("i-status").value, b = $("i-batch").value;
    // an item saved this session stays in view under a status filter it has just left
    return (!t || it.type === t) && (!b || it.batch === b) && (!stt || it.status === stt || it._touched);
  }
  // one block per backend row (its vessel named once), multi-row and row-less items after them
  function itemGroups(list) {
    var order = [], by = {};
    list.forEach(function (it) {
      var key = it.live_rows.length === 1 ? "row:" + it.live_rows[0] : "item:" + it.item_id;
      if (!by[key]) { by[key] = []; order.push(key); }
      by[key].push(it);
    });
    order.sort(function (a, b) {
      var ra = a.indexOf("row:") ? Infinity : +a.slice(4), rb = b.indexOf("row:") ? Infinity : +b.slice(4);
      return ra - rb;
    });
    return order.map(function (k) { return by[k]; });
  }
  function rowLinks(rows) {
    return rows.map(function (r) {
      var i = vesselIndexForRow(r);
      return i >= 0 ? '<a href="#" data-row="' + r + '" title="open in the queue">row ' + r + "</a>" : "row " + r;
    }).join(", ");
  }
  function renderItemList() {
    var list = D.items.filter(itemVisible);
    $("i-count").textContent = list.length + " of " + D.items.length + " items · " +
      D.items.filter(function (it) { return it.status === "open"; }).length + " open";
    $("item-list").innerHTML = itemGroups(list).map(function (g) {
      var head = "";
      if (g[0].live_rows.length === 1) {
        var i = vesselIndexForRow(g[0].live_rows[0]);
        head = '<h3 class="igroup">' + rowLinks(g[0].live_rows) + (i >= 0 ? " · " + esc(D.vessels[i].name || "(no name)") : "") +
          (g.length > 1 ? ' <span class="n">' + g.length + " items</span>" : "") + "</h3>";
      }
      return '<section class="igroup-box">' + head + g.map(itemHtml).join("") + "</section>";
    }).join("") || '<div class="empty">No items match.</div>';
  }
  function itemHtml(it) {
    var label = ITEM_TYPES[it.type] || it.type;
    // the title is worth showing only when it says more than the type chip does
    var generic = !it.title || it.title.toLowerCase() === label.toLowerCase() || it.title === "backend flag";
    var h = '<div class="item s-' + esc(it.status.replace(/ /g, "-")) + '" data-item="' + esc(it.item_id) + '"><div class="row1">' +
      '<span class="chip">' + esc(label) + "</span> " +
      (generic ? "" : '<span class="col">' + esc(it.title) + "</span> ") +
      (it.live_rows.length > 1 ? "<span>" + rowLinks(it.live_rows) + "</span> " : "") +
      '<span class="batch">' + "batch " + esc(batchOf(it.batch).label) + "</span></div>";
    if (it.detail) h += '<div class="detail">' + esc(it.detail) + "</div>";
    if (it.logged_call && it.logged_call !== it.conflict_decision)
      h += '<div class="detail"><span class="chip warn">call ' + esc(it.logged_call) + " is in review_items.jsonl but " +
        "conflicts.csv says " + esc(it.conflict_decision || "nothing") + " (apply_batch.py regenerated it) — press the call again to rewrite it</span></div>";
    if (it.urls.length) h += '<ul class="refs">' + it.urls.map(function (u) {
      return "<li>" + link(u) + "</li>";
    }).join("") + "</ul>";
    h += '<div class="controls">';
    if (it.conflict_match) {
      // AP §4: a conflict is decided by hand; the call lands in conflicts.csv `decision`
      h += '<span class="seg" title="written to conflicts.csv; an accepted conflict is still applied by hand (AP §4)">' +
        '<span class="k">call</span>' + ["accept", "hold", "reject"].map(function (c) {
          return '<button type="button" class="ctl ' + c + '" aria-pressed="' + (c === (it.conflict_decision || "hold")) +
            '" data-call="' + c + '">' + c + "</button>";
        }).join("") + "</span>";
    }
    h += '<span class="seg"><span class="k">status</span>' + ITEM_STATUSES.map(function (s) {
      return '<button type="button" class="ctl" aria-pressed="' + (s === it.status) + '" data-status="' + s + '">' + s + "</button>";
    }).join("") + "</span>";
    h += '<span class="saving">' + (it.last ? esc(it.last.reviewer) : "") + "</span>" +
      '<textarea data-f="note" rows="1" placeholder="note — saved when you leave the box">' +
      esc(it.last ? it.last.note || "" : "") + "</textarea></div></div>";
    return h;
  }
  function saveItem(box, change) {
    var id = box.getAttribute("data-item");
    var it = D.items.filter(function (x) { return x.item_id === id; })[0];
    var rec = {item_id: id, status: change.status || it.status, note: box.querySelector('[data-f="note"]').value};
    if (change.call) {
      rec.conflict_decision = change.call;
      // a call other than hold settles the conflict, unless it is parked for research
      if (!change.status && it.status === "open" && change.call !== "hold") rec.status = "resolved";
    }
    var msg = box.querySelector(".saving");
    msg.textContent = "Saving…";
    msg.className = "saving";
    Store.item([rec]).then(function (saved) {
      saved.forEach(function (r) {
        it.status = r.status;
        it.last = r;
        if (r.conflict_decision) { it.conflict_decision = r.conflict_decision; it.logged_call = r.conflict_decision; }
      });
      it._touched = true;
      S.itemSession = S.itemSession.concat(saved);
      var tmp = document.createElement("div");
      tmp.innerHTML = itemHtml(it);
      tmp.firstChild.querySelector(".saving").textContent = "saved";
      box.parentNode.replaceChild(tmp.firstChild, box);
      $("i-count").textContent = D.items.filter(itemVisible).length + " of " + D.items.length + " items · " +
        D.items.filter(function (x) { return x.status === "open"; }).length + " open";
    }).catch(function (err) {
      msg.textContent = "Not saved: " + err.message;
      msg.className = "err";
      box.classList.add("failed");
    });
  }
  function onItemClick(e) {
    var a = e.target.closest("a[data-row]");
    if (a) {
      e.preventDefault();
      showTab("queue");
      $("f-decision").value = "";            // the row may have nothing on hold
      refilter();
      return selectVessel(vesselIndexForRow(+a.getAttribute("data-row")));
    }
    var b = e.target.closest("button[data-status], button[data-call]");
    if (!b) return;
    saveItem(b.closest(".item"), {status: b.getAttribute("data-status"), call: b.getAttribute("data-call")});
  }
  function onItemNote(e) {
    if (e.target.matches('textarea[data-f="note"]')) saveItem(e.target.closest(".item"), {});
  }

  // ---- session summary ----
  function renderSummary() {
    var by = {};
    S.session.forEach(function (r) {
      var b = D.proposals[r.key].batch;
      by[b] = by[b] || {accept: 0, hold: 0, reject: 0, suggest: 0};
      by[b][r.decision]++;
    });
    var itemsBy = {};
    S.itemSession.forEach(function (r) {
      var b = r.item_id.split("::")[0];
      itemsBy[b] = (itemsBy[b] || 0) + 1;
    });
    var touched = uniq(Object.keys(by).concat(Object.keys(itemsBy))).sort(function (a, b) {
      return batchOf(a).apply_order - batchOf(b).apply_order;
    });
    var sugg = Object.keys(D.proposals).filter(function (k) { return D.proposals[k].decision === "suggest"; });
    var suggDirs = uniq(sugg.map(function (k) { return D.proposals[k].batch; }));
    var h = "<h2>This session</h2>";
    if (!touched.length) h += "<p>No decisions recorded yet this session.</p>";
    else {
      h += "<table><tr><th>batch</th><th>accept</th><th>hold</th><th>reject</th><th>suggest</th><th>items</th></tr>" +
        touched.map(function (b) {
          var c = by[b] || {accept: 0, hold: 0, reject: 0, suggest: 0};
          return "<tr><td>" + esc(batchOf(b).label) + (batchOf(b).label !== b ? "<br><code>" + esc(b) + "</code>" : "") + "</td><td>" + c.accept +
            "</td><td>" + c.hold + "</td><td>" + c.reject + "</td><td>" + c.suggest + "</td><td>" +
            (itemsBy[b] || 0) + "</td></tr>";
        }).join("") + "</table>";
    }
    var decTouched = touched.filter(function (b) { return by[b]; });
    h += "<h2>Next</h2>";
    if (decTouched.length) {
      h += "<p>Regenerate the apply artifacts from the new decisions (Apply SOP step 2), then apply and verify as usual:</p><pre>" +
        decTouched.map(function (b) { return "python scripts/apply_batch.py --batch batches/" + esc(b); }).join("\n") + "</pre>";
    } else h += "<p>No batch decisions changed this session, so no apply_batch.py run is needed.</p>";
    h += "<h2>Suggestions pending</h2>";
    if (sugg.length) {
      h += "<p>" + sugg.length + " line(s) set to suggest (stored as reject in decisions.csv). They reach the " +
        "backend only through a fix batch that re-gates them:</p><pre>python review_app/suggestions.py --batches " +
        suggDirs.map(function (b) { return "batches/" + esc(b); }).join(" ") +
        " --out work/review_suggestions_fix.json</pre><ul>" + sugg.map(function (k) {
          var p = D.proposals[k];
          return "<li>" + esc(p.column) + " · " + esc(batchOf(p.batch).label) + " · " +
            esc(p.suggestion ? p.suggestion.value : "") + "</li>";
        }).join("") + "</ul>";
    } else h += "<p>None.</p>";
    var open = D.items.filter(function (it) { return it.status !== "resolved"; }).length;
    h += "<h2>Items</h2><p>" + open + " of " + D.items.length + " items not resolved (statuses in each batch's " +
      "<code>review_items.jsonl</code>; conflict calls in <code>conflicts.csv</code> — note that " +
      "<code>apply_batch.py</code> regenerates conflicts.csv with every call back at hold).</p>";
    $("tab-summary").innerHTML = '<div class="summary">' + h + "</div>";
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
    if (name === "items") renderItems();
    if (name === "summary") renderSummary();
  }

  function banner(msg, ok) {
    var b = $("banner");
    b.classList.toggle("ok", !!ok);
    b.textContent = msg;
    b.hidden = !msg;
  }

  // ---- boot ----
  // Exposed for the later milestones and for debugging in the console.
  window.ReviewApp = {
    get data() { return D; }, state: S, refilter: refilter, renderCard: renderCard,
    matchingKeys: matchingKeys, suggestLine: suggestLine, filterDescription: filterDescription, dialog: dialog, banner: banner,
    bulkDecide: bulkDecide, showTab: showTab
  };

  initTheme();
  initTabs();
  document.addEventListener("keydown", onKey);
  $("card").addEventListener("click", onCardClick);
  $("card").addEventListener("toggle", function (e) {
    var l = e.target.closest && e.target.closest(".line");
    if (l && e.target.hasAttribute("data-more")) S.open[l.getAttribute("data-key")] = e.target.open;
  }, true);
  function adopt(data) {
    D = data;
    // a review_data.json built before the why / sources split: show the whole note and the bare refs
    Object.keys(D.proposals).forEach(function (k) {
      var p = D.proposals[k];
      if (p.why == null) { p.why = p.note || ""; p.detail = []; }
      if (!p.sources) p.sources = p.refs.map(function (x) {
        return {url: x.url, href: x.url, label: x.url, status: x.verdict ? "other" : "unchecked",
                reason: x.verdict || "", verdicts: [x.url + ": " + (x.verdict || "not checked")]};
      });
    });
    var pulledH = (Date.now() - new Date(D.backend_pulled).getTime()) / 36e5;
    $("built").textContent = pulledH > 24 ? "backend pulled " + Math.round(pulledH) + " h ago — sync" : "";
    $("built").title = "built " + D.built.replace("T", " ").slice(0, 16) +
      " · backend pulled " + D.backend_pulled.replace("T", " ").slice(0, 16);
    $("whoami").title = $("built").title;
    $("sync").title = "Re-pull the backend and settle what it already holds · last pulled " +
      D.backend_pulled.replace("T", " ").slice(0, 16);
  }
  // Sync: the server re-pulls and rebuilds, accepts the holds the backend already holds and
  // resolves the items it settles; the page then takes the new dataset in place (the session
  // summary and the filters stay).
  function syncBackend() {
    var b = $("sync");
    b.disabled = true;
    b.textContent = "syncing…";
    Store.refresh().then(function (r) {
      return Store.load().then(function (data) {
        adopt(data);
        refilter();
        if (!$("tab-items").hidden) renderItems();
        if (!$("tab-summary").hidden) renderSummary();
        var n = r.accepted.length, m = r.resolved.length;
        banner("Backend synced" + (n || m ? ": " + n + " held line" + (n === 1 ? "" : "s") +
          " already in the backend → accept, " + m + " item" + (m === 1 ? "" : "s") + " resolved."
          : " — nothing new was settled by it."), true);
      });
    }).catch(function (e) { banner("Sync failed, nothing changed: " + e.message); })
      .then(function () { b.disabled = false; b.textContent = "↻ sync backend"; });
  }
  $("sync").onclick = syncBackend;

  // Push: the server plans on a fresh pull; the dialog lists every cell that would change and
  // one confirmation writes exactly that plan (the token; a stale plan is refused, not written).
  function planTable(ws) {
    var byBatch = {}, order = [];
    ws.forEach(function (w) {
      if (!byBatch[w.batch]) { byBatch[w.batch] = []; order.push(w.batch); }
      byBatch[w.batch].push(w);
    });
    return order.map(function (b) {
      return '<h4>batch ' + esc(byBatch[b][0].label) + ' · ' + byBatch[b].length + '</h4><table class="plan">' +
        '<tr><th>row</th><th>vessel</th><th>column</th><th>now</th><th>→ becomes</th></tr>' +
        byBatch[b].map(function (w) {
          return '<tr><td>' + w.live_row + '</td><td>' + esc(w.name) + '</td><td>' + esc(w.column) +
            '</td><td class="old">' + (esc(w.old) || '<i>blank</i>') + '</td><td class="new">' + esc(w.new) + '</td></tr>';
        }).join("") + '</table>';
    }).join("");
  }
  function reload(msg, ok) {
    return Store.load().then(function (data) {
      adopt(data);
      refilter();
      if (!$("tab-items").hidden) renderItems();
      if (!$("tab-summary").hidden) renderSummary();
      banner(msg, ok);
    });
  }
  function pushAccepted() {
    var b = $("push");
    b.disabled = true;
    b.textContent = "planning…";
    var batch = $("f-batch").value;      // the Batch filter scopes the push
    var scope = batch ? " of batch " + ((D.batches.filter(function (x) { return x.dir === batch; })[0] || {}).label || batch) : "";
    Store.pushPlan(batch).then(function (plan) {
      var n = plan.writes.length, m = plan.applied_writes.length, k = plan.skipped.length;
      if (!n && !m) {
        return reload("Nothing to push: every accepted line" + scope + " is already in the backend" +
          (k ? " (" + k + " accepted line" + (k === 1 ? " stays" : "s stay") + " on the by-hand path)." : "."), true);
      }
      var html = '<h3>Push accepted lines' + esc(scope) + ' to the backend sheet</h3>' +
        '<p>' + n + ' cell' + (n === 1 ? "" : "s") + ' will be written to the live sheet. Rejects and holds write nothing.' +
        (batch ? "" : " Pick a batch in the Batch filter first to push one batch at a time.") + '</p>' +
        '<div class="planbox">' + planTable(plan.writes) +
        (m ? '<details><summary>' + m + ' more from batches already applied — the sheet differs, likely a later hand edit</summary>' +
          planTable(plan.applied_writes) + '</details>' : "") +
        (k ? '<details><summary>' + k + ' accepted line' + (k === 1 ? "" : "s") + ' not pushed (by-hand path)</summary><ul>' +
          plan.skipped.map(function (x) {
            return '<li>' + (x.live_row ? 'row ' + x.live_row + ' · ' : "") + esc(x.column) + ' — ' + esc(x.why) + '</li>';
          }).join("") + '</ul></details>' : "") + '</div>' +
        (m ? '<label class="check"><input type="checkbox" id="push-applied"> also overwrite the ' + m +
          ' cell' + (m === 1 ? "" : "s") + ' from applied batches</label>' : "");
      var label = n ? "write " + n + " cell" + (n === 1 ? "" : "s") : "write";
      return dialog(html, [["cancel", null], [label, function () {
        var inc = !!($("push-applied") && $("push-applied").checked);
        if (!n && !inc) return false;
        return {token: inc ? plan.token_all : plan.token, inc: inc};
      }]]).then(function (go) {
        if (!go) return reload("", true);
        b.textContent = "writing…";
        return Store.push(go.token, go.inc, batch).then(function (r) {
          var bad = r.mismatches.length;
          return reload(r.written + " cell" + (r.written === 1 ? "" : "s") + " written to the backend and verified" +
            (bad ? "; " + bad + " did NOT land (" + r.mismatches.slice(0, 5).map(function (w) {
              return "row " + w.live_row + " " + w.column; }).join(", ") + (bad > 5 ? ", …" : "") + ")" : ".") +
            (r.error ? " " + r.error : ""), !bad && !r.error);
        });
      });
    }).catch(function (e) { banner("Push: " + e.message); })
      .then(function () { b.disabled = false; b.textContent = "⇪ push accepted"; });
  }
  $("push").onclick = pushAccepted;

  Promise.all([Store.load(), Store.whoami()]).then(function (r) {
    ME = r[1];
    $("whoami").textContent = ME;
    adopt(r[0]);
    initFilters();
    refilter();
  }).catch(function (e) { banner("Could not load the review data: " + e.message); });
})();
