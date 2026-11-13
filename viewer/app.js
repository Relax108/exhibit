(() => {
  "use strict";
  const X = window.EXHIBIT;
  if (!X) {
    document.getElementById("panel").textContent = "The case data did not load (data.js is missing).";
    return;
  }
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const fmtDate = (iso) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    return m ? `${MONTHS[+m[2] - 1]} ${+m[3]}, ${m[1]}` : iso || "";
  };

  const lines = new Map(X.lines.map((l) => [l.id, l]));
  const pages = new Map(X.pages.map((p) => [`${p.doc}.${p.number}`, p]));
  const docs = new Map(X.documents.map((d) => [d.id, d]));
  const pageCount = (doc) => X.pages.filter((p) => p.doc === doc).length;
  const C = X.case;
  const Q = X.quality;

  // Every clickable fact is registered here and referenced by index.
  const facts = [];
  const reg = (field, label) => {
    facts.push({ ...field, label });
    return facts.length - 1;
  };
  const cls = (f) => (f.status !== "verified" ? "bad" : (f.evidence || "").startsWith("scan") ? "scan" : "");
  const factBtn = (field, label, text) => {
    if (!field || field.status === "absent") return "";
    const i = reg(field, label);
    const shown = text ?? field.value;
    return `<button class="fact ${cls(field)}" data-fact="${i}" title="Show where this comes from">${esc(shown)}</button>`;
  };

  // ---------------------------------------------------------------- summary
  const encs = C.encounters.filter((e) => e.verified);
  const first = encs[0]?.date.value, last = encs[encs.length - 1]?.date.value;
  const fc = C.fact_counts;
  $("#case-name").textContent = X.case_name;
  $("#summary").innerHTML = [
    ["Billed, verified line items", money(C.total_billed), `${Object.keys(C.billed_by_provider).length} providers, duplicates excluded`],
    ["Treatment dates", String(new Set(encs.map((e) => e.date.value)).size), `${fmtDate(first)} to ${fmtDate(last)}`],
    ["Findings to review", String(C.findings.length), C.findings.map((f) => f.type === "care_gap" ? "gap" : f.type === "duplicate_document" ? "duplicate" : f.type === "total_mismatch" ? "total" : "charge").join(", ")],
    ["Facts proven on the page", `${fc.verified} of ${fc.total}`, `${fc.from_scans} read from scans; ${fc.unsupported} unproven`],
    ["Model cost for this file", money(Q.cost.usd).replace(/(\.\d\d)\d*$/, "$1"), `${X.pages.length} pages, ${money(Q.cost.usd_per_page)} a page`],
  ].map(([k, v, s]) => `<div class="stat"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div><div class="s">${esc(s)}</div></div>`).join("");
  $("#findings-count").textContent = C.findings.length;

  // ---------------------------------------------------------------- views
  const chargesFor = (org, date) =>
    C.bills.filter((b) => b.org === org).flatMap((b) => b.lines.filter((l) => l.verified && l.date.value === date));

  const KIND = { emergency: "Emergency", imaging: "Imaging", office_visit: "Office visit", physical_therapy: "Physical therapy", procedure: "Procedure", other: "Other" };

  function chronology() {
    const gaps = new Map(C.findings.filter((f) => f.type === "care_gap").map((f) => [f.to, f]));
    let html = `<div class="legend">
      <span><i class="dot ok"></i>proven in the document's text</span>
      <span><i class="dot scan"></i>proven in a scan, re-read from a zoomed crop</span>
      <span><i class="dot bad"></i>not found on the cited page, so not counted</span></div><div class="timeline">`;
    let prevDate = null;
    for (const e of C.encounters) {
      const d = e.date.value;
      if (d !== prevDate && gaps.has(d)) {
        const g = gaps.get(d);
        html += `<div class="gapnote">${esc(g.days)} days with no documented treatment. ${esc("Insurers read gaps like this as recovery.")}</div>`;
      }
      prevDate = d;
      const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d) || [];
      const charges = chargesFor(e.org, d);
      const dx = e.diagnoses.map((c) => `<span class="chip ${c.code.status !== "verified" ? "bad" : ""}">${factBtn(c.code, "Diagnosis code", c.code.value)}<span>${esc(c.description)}</span></span>`).join("");
      const px = e.procedures.map((c) => `<span class="chip ${c.code.status !== "verified" ? "bad" : ""}">${factBtn(c.code, "Procedure code", c.code.value)}<span>${esc(c.description)}</span></span>`).join("");
      const kf = e.key_facts.filter((k) => k.status !== "absent").map((k) => `<li>${factBtn(k, "Quoted from the record")}</li>`).join("");
      const billed = charges.length
        ? `<div class="billed">Billed ${charges.map((c) => factBtn(c.charge, `Charge ${c.code.value}`, money(c.charge.value))).join(" + ")}${charges.length > 1 ? ` = ${money(charges.reduce((a, c) => a + Number(c.charge.value), 0))}` : ""}</div>`
        : "";
      html += `<article class="event">
        <div class="when"><div class="d">${factBtn(e.date, "Date of care", m[0] ? `${MONTHS[+m[2] - 1]} ${+m[3]}` : d)}</div><div class="y">${esc(m[1] || "")}</div></div>
        <div>
          <span class="kind">${esc(KIND[e.kind] || e.kind)}</span>
          <div class="who">${factBtn(e.provider, "Provider")}${e.clinician.status !== "absent" ? ` <span class="doc">&middot; ${factBtn(e.clinician, "Clinician")}</span>` : ""}</div>
          ${dx || px ? `<div class="chips">${dx}${px}</div>` : ""}
          ${kf ? `<ul class="facts">${kf}</ul>` : ""}
          ${billed}
        </div></article>`;
    }
    return html + "</div>";
  }

  function bills() {
    const nodoc = new Set(C.findings.filter((f) => f.type === "billed_not_documented").map((f) => `${f.provider}|${f.date}`));
    let html = "";
    for (const b of C.bills) {
      const sum = b.lines.filter((l) => l.verified).reduce((a, l) => a + Number(l.charge.value), 0);
      const mismatch = C.findings.find((f) => f.type === "total_mismatch" && f.doc === b.doc);
      html += `<section class="bill"><h3>${factBtn(b.provider, "Provider")}<small>${esc(docs.get(b.doc)?.title || b.doc)}${b.account.status !== "absent" ? " &middot; account " + factBtn(b.account, "Account") : ""}</small></h3>
        <table><thead><tr><th>Date</th><th>Code</th><th>Description</th><th class="r">Charge</th></tr></thead><tbody>
        ${b.lines.map((l) => `<tr class="${nodoc.has(`${b.org}|${l.date.value}`) ? "nodoc" : ""}">
            <td>${factBtn(l.date, "Date of service", fmtDate(l.date.value))}</td>
            <td>${factBtn(l.code, "Billing code")}</td>
            <td>${esc(l.description)}${l.units && l.units !== "1" ? ` <span class="mono">x${esc(l.units)}</span>` : ""}</td>
            <td class="r">${factBtn(l.charge, "Charge", money(l.charge.value))}</td></tr>`).join("")}
        </tbody></table>
        <div class="billfoot"><span>Line items: <b>${money(sum)}</b></span>
        ${b.printed_total.status !== "absent" ? `<span class="${mismatch ? "mismatch" : ""}">Printed total: ${factBtn(b.printed_total, "Printed total", money(b.printed_total.value))}${mismatch ? " (does not match)" : ""}</span>` : ""}</div></section>`;
    }
    for (const [dup, info] of Object.entries(X.duplicates)) {
      html += `<div class="excluded">${esc(docs.get(dup)?.title || dup)} is a copy of ${esc(docs.get(info.of)?.title || info.of)} and is left out of every total. <button class="show" data-doc="${esc(dup)}">Open it</button></div>`;
    }
    return html;
  }

  function findings() {
    return C.findings.map((f) => {
      const i = reg({ line_ids: f.line_ids, status: "verified", value: f.title, evidence: "" }, "Finding");
      return `<article class="finding ${f.severity === "info" ? "info" : ""}"><h3>${esc(f.title)}</h3><p>${esc(f.detail)}</p>
        ${f.line_ids.length ? `<button class="show" data-fact="${i}">Show on the page</button>` : ""}</article>`;
    }).join("") || "<p>No findings.</p>";
  }

  function quality() {
    const pct = (x) => Math.round(x * 100) + "%";
    const m = (k, v, s, key) => `<div class="metric ${key ? "key" : ""}"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div><div class="s">${esc(s)}</div></div>`;
    const ocr = Q.ocr || {};
    return `<div class="metrics">
      ${m("Facts marked proven that are wrong", String(Q.verified_but_wrong), "The number that must stay at zero", true)}
      ${m("Treatment dates found", `${Q.encounters.matched} of ${Q.encounters.expected}`, `precision ${pct(Q.encounters.precision)}, recall ${pct(Q.encounters.recall)}`)}
      ${m("Bill lines found", `${Q.bill_lines.matched} of ${Q.bill_lines.expected}`, `precision ${pct(Q.bill_lines.precision)}, recall ${pct(Q.bill_lines.recall)}`)}
      ${m("Diagnosis codes found", `${Q.diagnosis_codes.matched} of ${Q.diagnosis_codes.expected}`, `precision ${pct(Q.diagnosis_codes.precision)}, recall ${pct(Q.diagnosis_codes.recall)}`)}
      ${m("Total billed", Q.total_billed.exact ? "Exact" : "Off", `${money(Q.total_billed.exhibit)} against ${money(Q.total_billed.expected)} expected`)}
      ${m("Planted problems caught", `${Q.findings.found} of ${Q.findings.expected}`, Q.findings.false_alarms.length ? `false alarms: ${Q.findings.false_alarms.join(", ")}` : "no false alarms")}
      ${m("Scanned lines re-read", String(ocr.lines_reread ?? 0), `${ocr.lines_where_readings_differ ?? 0} where OCR and the zoomed re-read disagreed`)}
      ${m("Model cost and time", money(Q.cost.usd), `${Q.cost.calls} calls to ${Q.cost.model} (effort ${Q.cost.effort}), ${Q.cost.model_seconds}s of model time`)}
    </div>
    ${comparison()}
    <div class="prose">
      <p>The sample file is synthetic, so the right answer is known exactly, and these numbers come from comparing Exhibit's output with it, not from the model grading itself. It is also small (13 pages) and written by the same person who built the checks, so it shows that the checks work, not how the system would score on a thousand real files.</p>
      <h3>What running two models taught</h3>
      <p>The first version cropped each scanned line to the box the OCR drew around it. On one row that box started late and cut off the "3" of "3/16/26". Claude transcribed it as "[?]/16/26" and the date stayed unproven; Gemini wrote "3/16/26", right by luck, by guessing a digit it could not see. Crops now span the full width of the page, so no model has to choose between refusing and guessing.</p>
      <p>The file was built to contain the problems real record sets contain: a faxed duplicate bill, a bill whose printed total is $100 more than its charges, a therapy visit billed with no treatment note, a 33-day gap in treatment, and two scanned documents whose table of visit dates plain OCR misreads.</p>
    </div>`;
  }

  function comparison() {
    const runs = Object.entries(X.comparison || {});
    if (runs.length < 2) return "";
    const NAMES = { anthropic: "Claude Opus 5.5", gemini: "Gemini 3.5 Flash" };
    const row = ([name, q]) => `<tr>
      <td><b>${esc(NAMES[name] || q.cost.model)}</b>${name === "anthropic" ? " <span style='color:var(--faint)'>(shown)</span>" : ""}</td>
      <td class="r">${q.encounters.matched}/${q.encounters.expected}</td>
      <td class="r">${q.bill_lines.matched}/${q.bill_lines.expected}</td>
      <td class="r">${q.diagnosis_codes.matched}/${q.diagnosis_codes.expected}</td>
      <td class="r">${q.findings.found}/${q.findings.expected}</td>
      <td class="r">${q.verified_but_wrong}</td>
      <td class="r">${money(q.cost.usd)}</td>
      <td class="r">${Math.round(q.cost.model_seconds)}s</td></tr>`;
    return `<section class="bill"><h3>Same file, two models <small>effort "low" on both; cost at paid list prices</small></h3>
      <div style="overflow-x:auto"><table><thead><tr><th>Model</th><th class="r">Dates</th><th class="r">Bill lines</th><th class="r">Dx codes</th>
      <th class="r">Problems</th><th class="r">Wrong but proven</th><th class="r">Cost</th><th class="r">Model time</th></tr></thead>
      <tbody>${runs.map(row).join("")}</tbody></table></div>
      <div class="billfoot"><span style="color:var(--muted)">Gemini's time includes waiting out "busy" answers on its free tier.</span></div></section>`;
  }

  function how() {
    return `<div class="prose"><ol class="steps">
      <li><b>Read every page into positioned lines.</b> Digital PDFs are read from their text layer; scans go through OCR. Every line gets an id like <code>D06.p2.l7</code> and its box on the page.</li>
      <li><b>Re-read scanned lines from zoomed crops.</b> OCR misreads tables in scans, and its confidence score does not say when. Each OCR line is cut out at 300 dpi and read again by Claude. OCR keeps the position, the re-read supplies the text, and both are kept.</li>
      <li><b>Find duplicates before extracting.</b> A faxed copy of a bill matches its original letter for letter once spacing is ignored, so it is set aside before it can double the totals.</li>
      <li><b>Extract with citations.</b> Claude returns every date, provider, code, amount and quoted fact together with the ids of the lines it read them from, in a fixed schema.</li>
      <li><b>Prove every value in code.</b> A plain program checks that each value really appears in the lines it cites: dates in any printed format, amounts to the cent, codes exactly, quotes word for word. A value that fails is shown in red and counted nowhere.</li>
      <li><b>Reconcile bills with records.</b> Charges are matched to visits by provider and date, printed totals are re-added, and gaps in treatment are measured.</li>
      <li><b>Score against the answer key.</b> Precision, recall, the count of wrong-but-proven facts, and the cost of every model call.</li>
    </ol>
    <h3>What it does not do</h3>
    <p>It does not decide what a record means medically, and it does not write the demand letter. It gives the person who does a chronology and a bill summary they can trust, because every number is one click from its page.</p></div>`;
  }

  const VIEWS = { chronology, bills, findings, quality, how };
  function show(tab) {
    facts.length = 0;
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    $("#panel").innerHTML = VIEWS[tab]();
    try { localStorage.setItem("exhibit-tab", tab); } catch (e) {}
  }

  // ---------------------------------------------------------------- viewer
  const state = { doc: X.documents[0].id, page: 1, marks: [] };
  const sel = $("#doc-select");
  sel.innerHTML = X.documents.map((d) => `<option value="${esc(d.id)}">${esc(d.id)} &middot; ${esc(d.title)}${X.duplicates[d.id] ? " (duplicate)" : ""}</option>`).join("");

  function render(pulse) {
    const p = pages.get(`${state.doc}.${state.page}`);
    sel.value = state.doc;
    const img = $("#page-img");
    img.src = `pages/${state.doc}-p${state.page}.png`;
    img.alt = `${docs.get(state.doc).title}, page ${state.page}`;
    $("#page-label").textContent = `page ${state.page} of ${pageCount(state.doc)}`;
    $("#prev").disabled = state.page <= 1;
    $("#next").disabled = state.page >= pageCount(state.doc);
    const here = state.marks.map((id) => lines.get(id)).filter((l) => l && l.doc === state.doc && l.page === state.page);
    $("#marks").innerHTML = here.map((l) => {
      const [x0, y0, x1, y1] = l.bbox, pad = 2;
      const s = (v, total) => (v / total * 100).toFixed(3) + "%";
      return `<div class="hl ${pulse ? "pulse" : ""}" style="left:${s(x0 - pad, p.width)};top:${s(y0 - pad, p.height)};width:${s(x1 - x0 + 2 * pad, p.width)};height:${s(y1 - y0 + 2 * pad, p.height)}"></div>`;
    }).join("");
  }

  function go(doc, page, marks, pulse) {
    state.doc = doc; state.page = page; state.marks = marks || [];
    render(pulse);
  }

  function openFact(i, btn) {
    const f = facts[i];
    document.querySelectorAll(".fact.on").forEach((b) => b.classList.remove("on"));
    if (btn && btn.classList.contains("fact")) btn.classList.add("on");
    const cited = (f.line_ids || []).map((id) => lines.get(id)).filter(Boolean);
    const cite = $("#cite");
    if (!cited.length) {
      cite.innerHTML = `<span class="src">${esc(f.label)}: ${esc(f.value)}</span><span class="tagline bad">No source line was cited, so this value is not counted.</span>`;
      return;
    }
    const groups = [];
    for (const l of cited) {
      const key = `${l.doc}.${l.page}`;
      if (!groups.find((g) => g.key === key)) groups.push({ key, doc: l.doc, page: l.page });
    }
    go(groups[0].doc, groups[0].page, cited.map((l) => l.id), true);
    const tag = f.status !== "verified"
      ? `<span class="tagline bad">Not found on the cited lines (${esc(f.reason || "unproven")}). Not counted.</span>`
      : (f.evidence || "").startsWith("scan")
        ? `<span class="tagline scan">Proven in a scan, re-read from a zoomed crop. Check the highlighted line.</span>`
        : f.evidence ? `<span class="tagline ok">Proven in the document's text.</span>` : "";
    const quote = cited.slice(0, 3).map((l) => `<span class="mono">${esc(l.id)}</span> ${esc(l.text)}${l.ocr_text && l.ocr_text !== l.text ? ` <span style="color:var(--faint)">(OCR read: ${esc(l.ocr_text)})</span>` : ""}`).join("<br>");
    cite.innerHTML = `<span class="src">${esc(f.label)}: <b>${esc(f.value)}</b></span>${quote}${cited.length > 3 ? `<br>and ${cited.length - 3} more lines` : ""}<br>${tag}
      ${groups.length > 1 ? `<div class="also">${groups.map((g) => `<button data-go="${esc(g.doc)}|${g.page}">${esc(docs.get(g.doc).title)}, p${g.page}</button>`).join("")}</div>` : ""}`;
    if (window.matchMedia("(max-width: 1020px)").matches) $("#sheet").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---------------------------------------------------------------- events
  document.addEventListener("click", (ev) => {
    const t = ev.target.closest("[data-fact],[data-tab],[data-doc],[data-go]");
    if (!t) return;
    if (t.dataset.tab) return show(t.dataset.tab);
    if (t.dataset.fact !== undefined) return openFact(Number(t.dataset.fact), t);
    if (t.dataset.doc) return go(t.dataset.doc, 1, [], false);
    if (t.dataset.go) {
      const [d, p] = t.dataset.go.split("|");
      return go(d, Number(p), state.marks, true);
    }
  });
  sel.addEventListener("change", () => go(sel.value, 1, [], false));
  $("#prev").addEventListener("click", () => { if (state.page > 1) { state.page--; render(false); } });
  $("#next").addEventListener("click", () => { if (state.page < pageCount(state.doc)) { state.page++; render(false); } });

  const themeBtn = $("#theme");
  const setTheme = (t) => {
    document.documentElement.dataset.theme = t;
    themeBtn.textContent = t === "dark" ? "Light" : "Dark";
    try { localStorage.setItem("exhibit-theme", t); } catch (e) {}
  };
  themeBtn.addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
  setTheme(document.documentElement.dataset.theme || "light");

  let tab = "chronology";
  try { tab = localStorage.getItem("exhibit-tab") || tab; } catch (e) {}
  show(VIEWS[tab] ? tab : "chronology");
  render(false);
})();
