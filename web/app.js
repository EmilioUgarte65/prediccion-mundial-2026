/* ===== Predicción Mundial 2026 — front-end ===== */

// Nombre de selección -> código ISO (para bandera emoji). Casos especiales: Inglaterra/Escocia.
const TEAM_CODE = {
  "Mexico": "MX", "South Africa": "ZA", "South Korea": "KR", "Czech Republic": "CZ",
  "Canada": "CA", "Bosnia and Herzegovina": "BA", "Qatar": "QA", "Switzerland": "CH",
  "Brazil": "BR", "Morocco": "MA", "Haiti": "HT", "Scotland": "_SCO",
  "United States": "US", "Paraguay": "PY", "Australia": "AU", "Turkey": "TR",
  "Germany": "DE", "Curaçao": "CW", "Ivory Coast": "CI", "Ecuador": "EC",
  "Netherlands": "NL", "Japan": "JP", "Sweden": "SE", "Tunisia": "TN",
  "Belgium": "BE", "Egypt": "EG", "Iran": "IR", "New Zealand": "NZ",
  "Spain": "ES", "Cape Verde": "CV", "Saudi Arabia": "SA", "Uruguay": "UY",
  "France": "FR", "Senegal": "SN", "Iraq": "IQ", "Norway": "NO",
  "Argentina": "AR", "Algeria": "DZ", "Austria": "AT", "Jordan": "JO",
  "Portugal": "PT", "DR Congo": "CD", "Uzbekistan": "UZ", "Colombia": "CO",
  "England": "_ENG", "Croatia": "HR", "Ghana": "GH", "Panama": "PA",
};
const NAME_ES = {
  "Mexico": "México", "South Africa": "Sudáfrica", "South Korea": "Corea del Sur",
  "Czech Republic": "Chequia", "Canada": "Canadá", "Bosnia and Herzegovina": "Bosnia",
  "Qatar": "Catar", "Switzerland": "Suiza", "Brazil": "Brasil", "Morocco": "Marruecos",
  "Haiti": "Haití", "Scotland": "Escocia", "United States": "Estados Unidos",
  "Paraguay": "Paraguay", "Australia": "Australia", "Turkey": "Turquía",
  "Germany": "Alemania", "Curaçao": "Curazao", "Ivory Coast": "Costa de Marfil",
  "Ecuador": "Ecuador", "Netherlands": "Países Bajos", "Japan": "Japón",
  "Sweden": "Suecia", "Tunisia": "Túnez", "Belgium": "Bélgica", "Egypt": "Egipto",
  "Iran": "Irán", "New Zealand": "Nueva Zelanda", "Spain": "España",
  "Cape Verde": "Cabo Verde", "Saudi Arabia": "Arabia Saudita", "Uruguay": "Uruguay",
  "France": "Francia", "Senegal": "Senegal", "Iraq": "Irak", "Norway": "Noruega",
  "Argentina": "Argentina", "Algeria": "Argelia", "Austria": "Austria", "Jordan": "Jordania",
  "Portugal": "Portugal", "DR Congo": "RD Congo", "Uzbekistan": "Uzbekistán",
  "Colombia": "Colombia", "England": "Inglaterra", "Croatia": "Croacia",
  "Ghana": "Ghana", "Panama": "Panamá",
};

function flagSlug(team) {
  const code = TEAM_CODE[team];
  if (code === "_ENG") return "gb-eng";
  if (code === "_SCO") return "gb-sct";
  if (!code) return null;
  return code.toLowerCase();
}
// Imagen de bandera real (flagcdn). Fallback automático al código (texto alt) si no carga.
function flag(team, cls = "fl-sm") {
  const slug = flagSlug(team);
  const code = (TEAM_CODE[team] || "??").replace("_", "");
  if (!slug) return `<span class="flagimg ${cls} flag-fallback">${code}</span>`;
  return `<img class="flagimg ${cls}" loading="lazy" alt="${code}" ` +
         `src="https://flagcdn.com/${slug}.svg" ` +
         `onerror="this.outerHTML='<span class=&quot;flagimg ${cls} flag-fallback&quot;>${code}</span>'">`;
}
// Nombres cortos para tarjetas estrechas del bracket
const SHORT_NAME = {
  "United States": "EE.UU.", "Bosnia and Herzegovina": "Bosnia",
  "Ivory Coast": "C. Marfil", "Cape Verde": "C. Verde", "Saudi Arabia": "Arabia S.",
  "Netherlands": "P. Bajos", "South Korea": "Corea S.", "South Africa": "Sudáfrica",
  "Czech Republic": "Chequia", "New Zealand": "N. Zelanda", "DR Congo": "RD Congo",
};
const esName = t => NAME_ES[t] || t;
const shortName = t => SHORT_NAME[t] || NAME_ES[t] || t;
const pct = x => (x * 100).toFixed(0) + "%";
const pct1 = x => (x * 100).toFixed(1) + "%";

const ROUND_LABELS = {
  R32: "Ronda de 32", R16: "Octavos", QF: "Cuartos",
  SF: "Semifinal", Final: "Final", third: "3er lugar",
};

let DATA = null, BT = null, STATS = null, PERF = null, PED = null;
let TVAL = null;          // validación de minutos de gol
let REAL = null;          // datos reales 2026 (goleadores/árbitros)
let V2026 = null;         // validación del modelo solo-2026
let TMODEL = "ens";       // modelo elegido para comparar en el modal del torneo
let CURRENT_MT = null;    // partido abierto en el modal
let BMODEL = "ens";       // modelo que arma el CUADRO de eliminatorias
let BET_STAKE = 200;      // monto que el usuario quiere apostar (apartado Apuestas)
// devuelve HTML con lo que ganarías: recibes total y ganancia neta, para una cuota
function winHTML(odd) {
  const ret = Math.round(BET_STAKE * odd), profit = Math.round(BET_STAKE * (odd - 1));
  return `<span class="win"><b>$${ret}</b> <small>(ganas $${profit})</small></span>`;
}
function setStake(v) {
  const n = Math.max(1, Math.round(+v || 0));
  BET_STAKE = n;
  renderBets();
  const inp = document.getElementById("stakeInput");
  if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
}

function activeBracket() {
  return (DATA.brackets && DATA.brackets[BMODEL]) || DATA.bracket;
}
function setBModel(m) {
  BMODEL = m; TMODEL = m;  // el modal hereda el mismo modelo
  renderBracket();
}
let VALID_MODEL = "ens";  // modelo mostrado en la tabla de validación
const VMODELS = {
  ens:   { p: "e",  n: "🔀 Ensemble" },
  xgb:   { p: "p",  n: "🤖 XGBoost" },
  stat:  { p: "s",  n: "📊 Estadístico" },
  elo:   { p: "el", n: "📈 Elo" },
  y2026: { p: "y",  n: "🆕 Solo 2026" },
};

Promise.all([
  fetch("data/predictions.json").then(r => r.json()),
  fetch("data/backtest.json").then(r => r.ok ? r.json() : null).catch(() => null),
  fetch("data/tournament_stats.json").then(r => r.ok ? r.json() : null).catch(() => null),
  fetch("data/player_performance.json").then(r => r.ok ? r.json() : null).catch(() => null),
  fetch("data/wc_pedigree.json").then(r => r.ok ? r.json() : null).catch(() => null),
  fetch("data/timing_validation.json").then(r => r.ok ? r.json() : null).catch(() => null),
  fetch("data/real_2026.json").then(r => r.ok ? r.json() : null).catch(() => null),
  fetch("data/validation_2026.json").then(r => r.ok ? r.json() : null).catch(() => null),
])
  .then(([d, bt, st, pf, pe, tv, rl, v26]) => { DATA = d; BT = bt; STATS = st; PERF = pf; PED = pe; TVAL = tv; REAL = rl; V2026 = v26; init(); })
  .catch(e => {
    document.getElementById("bracketEl").innerHTML =
      `<p class="tl-empty">No se pudo cargar data/predictions.json. Ejecuta el pipeline (build.py) y sirve la carpeta web con un servidor local.</p>`;
    console.error(e);
  });

function init() {
  renderChips();
  renderBracket();
  renderGroups();
  renderGroupPlayed();
  renderGroupPredictions();
  renderAdvancement();
  renderBacktest();
  renderStats();
  renderBets();
  setupTabs();
  const t = new URLSearchParams(location.search).get("tab");
  if (t && document.querySelector(`.tab[data-panel="${t}"]`)) selectTab(t);
  setupModal();
  setupTableZoom();
  openFromHash();
  window.addEventListener("hashchange", openFromHash);
}

function allMatches() {
  return [...Object.values(activeBracket()).flat(), ...(DATA.group_predictions || [])];
}
function openFromHash() {
  const m = location.hash.match(/^#match-(\d+)/);
  if (!m) { document.getElementById("overlay").classList.remove("open"); return; }
  const mt = allMatches().find(x => String(x.match) === m[1]);
  if (mt) openModal(mt);
}

function renderChips() {
  const m = DATA.meta;
  const el = document.getElementById("chips");
  el.innerHTML = `
    <span class="chip">Datos hasta <b>${m.data_through}</b></span>
    <span class="chip">Grupos <b>${m.matches_played}</b> jugados · <b>${m.matches_remaining_group}</b> por jugar</span>
    <span class="chip">${m.n_sims.toLocaleString()} simulaciones</span>
    <span class="chip">Campeón <b>${esName(m.champion_pick)}</b> ${flag(m.champion_pick)}</span>`;
  document.getElementById("footMeta").textContent =
    `log-loss ${m.model_metrics.log_loss.toFixed(3)} · MAE goles ${m.model_metrics.goals_mae.toFixed(2)} · ` +
    `${m.n_match_sims.toLocaleString()} sims por partido`;
}

/* ---------- Bracket clásico (simétrico, copa al centro) ---------- */
// Reparto de partidos por mitades según el cuadro oficial.
const BR_LEFT = { r32: [74, 77, 73, 75, 83, 84, 81, 82], r16: [89, 90, 93, 94],
                  qf: [97, 98], sf: [101] };
const BR_RIGHT = { r32: [76, 78, 79, 80, 86, 88, 85, 87], r16: [91, 92, 95, 96],
                   qf: [99, 100], sf: [102] };

function mById(round) {
  const m = {};
  (activeBracket()[round] || []).forEach(x => { m[x.match] = x; });
  return m;
}

function bracketModelSelHTML() {
  if (!DATA.brackets) return "";
  const champ = (DATA.champions && DATA.champions[BMODEL]) || "";
  const btns = ["ens", "xgb", "stat", "elo", "y2026"].map(m =>
    `<button class="mdl-btn${m === BMODEL ? " on" : ""}" onclick="setBModel('${m}')">${VMODELS[m].n}</button>`).join("");
  return `<div class="bmsel">
    <span class="bmsel-lbl">Modelo del cuadro:</span> ${btns}
    ${champ ? `<span class="bmsel-champ">🏆 Campeón: <b>${esName(champ)}</b></span>` : ""}
  </div>`;
}

function renderBracket() {
  const sel = document.getElementById("bracketModelSel");
  if (sel) sel.innerHTML = bracketModelSelHTML();
  const R32 = mById("R32"), R16 = mById("R16"), QF = mById("QF"),
        SF = mById("SF"), FIN = mById("Final");
  const el = document.getElementById("bracketEl");
  el.className = "bracket2";
  el.innerHTML = "";

  const left = document.createElement("div");
  left.className = "half left";
  left.appendChild(bcol("16avos", BR_LEFT.r32.map(i => R32[i]), false));
  left.appendChild(bcol("8vos", BR_LEFT.r16.map(i => R16[i]), false));
  left.appendChild(bcol("4tos", BR_LEFT.qf.map(i => QF[i]), false));
  left.appendChild(bcol("Semi", BR_LEFT.sf.map(i => SF[i]), false));

  const right = document.createElement("div");
  right.className = "half right";
  right.appendChild(bcol("Semi", BR_RIGHT.sf.map(i => SF[i]), true));
  right.appendChild(bcol("4tos", BR_RIGHT.qf.map(i => QF[i]), true));
  right.appendChild(bcol("8vos", BR_RIGHT.r16.map(i => R16[i]), true));
  right.appendChild(bcol("16avos", BR_RIGHT.r32.map(i => R32[i]), true));

  el.appendChild(left);
  el.appendChild(centerCol(FIN[104]));
  el.appendChild(right);
}

function bcol(label, matches, mirror) {
  const col = document.createElement("div");
  col.className = "bcol";
  col.innerHTML = `<div class="bcol-head">${label}</div>`;
  const wrap = document.createElement("div");
  wrap.className = "bcol-matches";
  matches.forEach(mt => {
    const slot = document.createElement("div");
    slot.className = "slot";
    if (mt) slot.appendChild(bcard(mt, mirror));
    wrap.appendChild(slot);
  });
  col.appendChild(wrap);
  return col;
}

function bcard(mt, mirror) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "bcard" + (mirror ? " mirror" : "");
  card.setAttribute("aria-label",
    `${esName(mt.teamA)} contra ${esName(mt.teamB)}, ver predicción`);
  if (mt.real) card.classList.add("played");
  const aWin = mt.winner === mt.teamA;
  const tag = mt.decided === "pens" ? `pen ${mt.penA}-${mt.penB}`
            : mt.decided === "ET" ? "pror." : "";
  // Badge de resultado real (jugado) + si el modelo acertó el ganador
  const realBadge = mt.real
    ? `<div class="breal ${mt.hit ? "ok" : "no"}" title="${
        mt.hit ? "El modelo acertó el ganador"
               : "El modelo falló: había previsto a " + esName(mt.predWinner)}">${
        mt.hit ? "✓ acertó" : "✗ falló · iba " + shortName(mt.predWinner)}</div>`
    : "";
  const row = (team, score, win) => {
    const fl = flag(team), nm = `<span class="bname">${shortName(team)}</span>`,
          sc = `<span class="bscore">${score}</span>`;
    const inner = mirror ? `${sc}${nm}${fl}` : `${fl}${nm}${sc}`;
    return `<div class="brow ${win ? "win" : "lose"}">${inner}</div>`;
  };
  card.innerHTML = realBadge + (tag ? `<div class="btag">${tag}</div>` : "")
    + row(mt.teamA, mt.scoreA, aWin) + row(mt.teamB, mt.scoreB, !aWin);
  card.addEventListener("click", () => { location.hash = `match-${mt.match}`; });
  return card;
}

function centerCol(finalMatch) {
  const champ = finalMatch ? finalMatch.winner : null;
  const odds = DATA.advancement.find(a => a.team === champ)?.Champion;
  const col = document.createElement("div");
  col.className = "center-col";
  col.innerHTML = `
    <div class="trophy-big" aria-hidden="true">
      <svg width="58" height="58" viewBox="0 0 24 24" fill="none" stroke="#f5b301" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 9a6 6 0 0 0 12 0V4H6z"/><path d="M6 5H3v2a3 3 0 0 0 3 3"/>
        <path d="M18 5h3v2a3 3 0 0 1-3 3"/><path d="M12 15v4"/><path d="M8 21h8"/><path d="M9 19h6"/>
      </svg>
    </div>
    <div class="final-label">FINAL</div>`;
  if (finalMatch) col.appendChild(bcard(finalMatch, false));
  const champBox = document.createElement("div");
  champBox.className = "champ-box";
  champBox.innerHTML = `
    <div class="champ-label">★ CAMPEÓN ★</div>
    <div class="champ-flag">${flag(champ, "fl-lg")}</div>
    <div class="champ-name">${esName(champ)}</div>
    <div class="champ-odds">${odds ? pct1(odds) + " prob. título" : ""}</div>`;
  col.appendChild(champBox);
  return col;
}

/* ---------- Apuestas ---------- */
function _evTag(ev) {
  const p = Math.round(ev * 100);
  return `<span class="ev ${ev > 0 ? "pos" : "neg"}">${p > 0 ? "+" : ""}${p}% valor</span>`;
}
function _pickLabel(name) { return name === "Empate" ? "Empate" : "Gana " + esName(name); }

function renderBets() {
  const el = document.getElementById("betsEl");
  if (!el) return;
  const B = DATA && DATA.bets;
  if (!B || !B.matches || !B.matches.length) {
    el.innerHTML = `<p class="tl-empty">No hay cuotas de próximos partidos. Corre <code>python src/fetch_odds.py</code> y <code>build.py</code>.</p>`;
    return;
  }
  const mk = BT && BT.metrics_eligible && BT.metrics_eligible.markets;
  const t = B.top;
  const hero = t ? `<div class="bet-hero">
    <div class="bh-label">⭐ La mejor apuesta ahora mismo</div>
    <div class="bh-main">${flag(t.home)} ${esName(t.home)} <span class="vs">vs</span> ${flag(t.away)} ${esName(t.away)}</div>
    <div class="bh-pick">${_pickLabel(t.name)} <b>@ ${t.odd}</b></div>
    <div class="bh-meta">Prob. del modelo <b>${pct(t.prob)}</b> · ${_evTag(t.ev)}</div>
    <div class="bh-win">Con $${BET_STAKE} recibes ${winHTML(t.odd)}</div>
  </div>` : "";
  const stakeBox = `<div class="stake-box">
    <span class="stake-lbl">💵 ¿Cuánto quieres apostar?</span>
    <span class="stake-in">$ <input id="stakeInput" type="number" min="1" step="10" value="${BET_STAKE}"
      inputmode="numeric" onchange="setStake(this.value)"> MXN</span>
    <span class="stake-quick">${[100, 200, 500, 1000].map(v =>
      `<button class="sq ${v === BET_STAKE ? "on" : ""}" onclick="setStake(${v})">$${v}</button>`).join("")}</span>
    <span class="stake-hint">Las ganancias se calculan con este monto.</span>
  </div>`;
  const rel = mk ? `<div class="bet-note">📊 <b>Fiabilidad medida</b> (validación walk-forward): ganador <b>~85%</b> <small>(cuando hay favorito claro)</small> · goles O/U <b>${pct(mk.goals.ens.ou_acc)}</b> · tarjetas <b>${pct(mk.cards.ou_acc)}</b> <small>(tiende a sobrestimar)</small> · córners <b>${pct(mk.corners.ens.ou_acc)}</b> <small>(poco fiable, evítalo)</small>.</div>` : "";

  const valueHTML = B.value && B.value.length ? B.value.map(v => `
    <div class="bet-row"><span class="br-teams">${flag(v.home)} ${esName(v.home)} <small>vs</small> ${flag(v.away)} ${esName(v.away)}</span>
      <span class="br-pick">${_pickLabel(v.name)} @ ${v.odd}</span>
      <span class="br-prob">${pct(v.prob)}</span>${_evTag(v.ev)}</div>`).join("")
    : `<p class="bet-empty">Sin apuestas de valor claras ahora (la casa está ajustada). Mira las seguras y los mercados.</p>`;

  const safeHTML = B.safe.slice(0, 6).map(s => `
    <div class="bet-row"><span class="br-teams">${flag(s.home)} ${esName(s.home)} <small>vs</small> ${flag(s.away)} ${esName(s.away)}</span>
      <span class="br-pick">${_pickLabel(s.name)} @ ${s.odd}</span>
      <span class="br-prob">${pct(s.prob)}</span>${_evTag(s.ev)}</div>`).join("");

  const confHTML = B.confidence.filter(c => c.market !== "corners").slice(0, 8).map(c => `
    <div class="bet-row"><span class="br-teams">${c.ico} ${flag(c.home)} ${esName(c.home)} <small>vs</small> ${flag(c.away)} ${esName(c.away)}</span>
      <span class="br-pick">${c.pick} <small>(esp. ${c.exp})</small></span>
      <span class="br-prob">${pct(c.prob)}</span></div>`).join("");

  // Tarjetas por partido (clic -> cuadro completo de qué conviene)
  const matchesHTML = B.matches.map((m, i) => {
    const r = m.rec[0];
    const ico = r.m.split(" ")[0];
    const lbl = r.m.replace(/^\S+\s/, "");
    const q = m.result90;
    const q90 = q.pick === "X" ? "🤝 Empate" : "🏆 Gana " + shortName(q.label);
    return `<button type="button" class="betmatch" data-i="${i}">
      <div class="bm-teams">${flag(m.home)} ${shortName(m.home)} <span class="vs">v</span> ${flag(m.away)} ${shortName(m.away)}</div>
      ${m.date ? `<div class="bm-date">${m.date.slice(5)}</div>` : ""}
      <div class="bm-r90">90 min: <b>${q90}</b> <span class="bm-p">${pct(q.prob)}</span></div>
      <div class="bm-top">${ico} <span class="bm-lbl">${lbl}:</span> <b>${r.pick}</b> <span class="bm-p">${pct(r.prob)}</span></div>
      <div class="bm-hint">toca para ver todo →</div>
    </button>`;
  }).join("");

  // Combinaciones (parlays): más pago manteniendo seguridad
  const C = B.combos;
  const comboRow = (x) => {
    const legs = x.legs.map(l =>
      `${l.sel === "X" ? "🤝 Empate" : flag(l.name) + " " + esName(l.name)} <span class="cl-odd">@${l.odd}</span>`).join(" &nbsp;+&nbsp; ");
    return `<div class="combo-row">
      <div class="cr-legs">${legs}</div>
      <div class="cr-meta">
        <span class="cr-prob">${pct(x.prob)} prob.</span>
        <span class="cr-odd">cuota ${x.odd}</span>
        <span class="cr-pay">$${BET_STAKE}→<b>$${Math.round(BET_STAKE * x.odd)}</b> <small>(+$${Math.round(BET_STAKE * (x.odd - 1))})</small></span>
        ${_evTag(x.ev)}</div>
    </div>`;
  };
  const combosHTML = C ? `
    <h3 class="bet-h" style="margin-top:22px">🧮 Combinaciones — más pago sin perder seguridad <small>(con $${BET_STAKE})</small></h3>
    <div class="bet-2col">
      <div class="bet-block"><h4 class="combo-h">🛡️ Más seguras</h4>${C.safest.slice(0,4).map(comboRow).join("")}</div>
      <div class="bet-block"><h4 class="combo-h">⚖️ Mejor equilibrio <small>(segura + paga bien)</small></h4>${(C.balanced.length?C.balanced:C.safest).slice(0,4).map(comboRow).join("")}</div>
    </div>
    <div class="bet-block"><h4 class="combo-h">💰 Mayor pago <small>(más riesgo)</small></h4>${C.payout.slice(0,4).map(comboRow).join("")}</div>
    <p class="bet-note" style="margin-top:6px">La prob. conjunta es el producto de cada partido (son independientes): a más partidos, más pago pero menos seguro. Una combinada falla entera si falla UNA pata.</p>` : "";

  el.innerHTML = stakeBox + hero + rel + `
    <div class="bet-actions"><button id="dlQuiniela" class="dl-btn">⬇️ Descargar quiniela (CSV)</button></div>
    <h3 class="bet-h">📋 Partidos — toca una tarjeta para ver <b>qué te conviene apostar</b></h3>
    <div class="betmatch-grid">${matchesHTML}</div>
    ${combosHTML}
    <p class="bet-disclaimer">⚠️ Apuestas sujetas a azar. El modelo da probabilidades, no certezas. Apuesta solo lo que puedas permitirte perder. +18.</p>`;

  el.querySelectorAll(".betmatch").forEach(btn =>
    btn.addEventListener("click", () => openBetModal(B.matches[+btn.dataset.i])));
  const dl = document.getElementById("dlQuiniela");
  if (dl) dl.addEventListener("click", downloadQuiniela);
}

function openBetModal(m) {
  const modal = document.getElementById("modal");
  modal.classList.remove("modal--table");
  const recHTML = m.rec.map(r =>
    `<div class="brec"><span class="brec-m">${r.m}</span> <b>${r.pick}</b>
      <span class="brec-p">${pct(r.prob)}</span> <span class="brec-rel">${r.rel}</span></div>`).join("");
  const x12 = m.x12.all.map(e => {
    const val = e.edge > 0.03 && e.prob >= 0.35;
    const nm = e.sel === "1" ? esName(m.home) : e.sel === "2" ? esName(m.away) : "Empate";
    return `<tr class="${val ? "dv-val" : ""}"><td class="l">${nm}</td><td>${e.odd}</td>
      <td>${pct(e.prob)}</td><td>${pct(e.fair)}</td>
      <td class="${e.edge > 0 ? "pos" : "neg"}">${e.edge > 0 ? "+" : ""}${Math.round(e.edge * 100)}%</td>
      <td class="win-cell">$${Math.round(BET_STAKE * e.odd)}</td></tr>`;
  }).join("");
  const lines = (arr, best) => arr.map(l => {
    const pk = best && best.line === l.l;
    return `<div class="oul ${pk ? "oul-best" : ""}"><span class="oul-l">±${l.l}</span>
      <span class="ov">Más ${pct(l.over)}</span><span class="un">Menos ${pct(1 - l.over)}</span></div>`;
  }).join("");
  modal.innerHTML = `
    <div class="modal-head"><div>
      <h3 id="mTitle">${flag(m.home)} ${esName(m.home)} <span class="vs">vs</span> ${flag(m.away)} ${esName(m.away)}</h3>
      <span class="mh-sub">${m.date ? "Partido " + m.date.slice(5) + " · " : ""}goles esperados ${m.xgA}–${m.xgB}</span>
    </div><button class="modal-x" onclick="closeModal()" aria-label="Cerrar">✕</button></div>
    <div class="modal-body">
      <div class="block bet-rec"><p class="block-title">💡 Qué te conviene apostar</p>${recHTML}</div>
      <div class="block r90-block"><p class="block-title">🏁 Resultado a 90 minutos (mercado 1X2)</p>
        <div class="r90-head">${m.result90.pick === "X" ? "🤝 Empate" : "🏆 Gana " + esName(m.result90.label)}
          <b>${pct(m.result90.prob)}</b> <small>· prob. de empate ${pct(m.result90.draw)}</small></div>
        <p class="mini-note">⚠️ El mercado <b>1X2</b> se paga <b>solo con 90 min</b> (prórroga y penales NO cuentan).
          En eliminatorias, para apostar a <b>quién avanza</b> usa el mercado <b>"Para clasificar"</b>.</p></div>
      <div class="block"><p class="block-title">Ganador (1X2) — modelo vs casa <b>sin vig</b></p>
        <table class="devig"><thead><tr><th class="l">Resultado</th><th>Cuota</th><th>Modelo</th><th>Justo</th><th>Ventaja</th><th>Recibes</th></tr></thead>
        <tbody>${x12}</tbody></table>
        <p class="mini-note">Verde = el modelo ve valor (ventaja &gt; 3%). "Recibes" = lo que te dan con tu apuesta de $${BET_STAKE} (incluye lo apostado).</p></div>
      <div class="block"><p class="block-title">⚽ Goles totales <span class="rel-tag">fiable 80%</span></p>${lines(m.goalsLines, m.goals)}</div>
      <div class="block"><p class="block-title">🟨 Tarjetas <span class="rel-tag">fiable 76%</span></p>${lines(m.cardsLines, m.cards)}</div>
      <div class="block"><p class="block-title">🤝 Ambos anotan</p>
        <div class="oul"><span class="oul-l"></span><span class="ov">Sí ${pct(m.btts)}</span><span class="un">No ${pct(1 - m.btts)}</span></div></div>
      <div class="block"><p class="block-title">Goles por equipo</p>
        <p class="tt-name">${esName(m.teamA.name)}</p>${lines(m.teamA.lines)}
        <p class="tt-name">${esName(m.teamB.name)}</p>${lines(m.teamB.lines)}</div>
      <div class="block"><p class="block-title">🚩 Córners <span class="rel-tag warn">poco fiable — evítalo</span></p>${lines(m.cornersLines, m.corners)}</div>
    </div>`;
  document.getElementById("overlay").classList.add("open");
}

function downloadQuiniela() {
  const B = DATA && DATA.bets;
  if (!B) return;
  const clean = (s) => String(s).replace(/[^\x00-\x7Fáéíóúñ ]/gi, "").trim();
  const rows = [["Partido", "Fecha", "Mercado", "Apuesta", "Prob modelo", "Fiabilidad"]];
  B.matches.forEach(m => m.rec.forEach(r =>
    rows.push([`${esName(m.home)} vs ${esName(m.away)}`, m.date, clean(r.m),
               clean(r.pick), Math.round(r.prob * 100) + "%", r.rel])));
  rows.push([]);
  rows.push(["COMBINACIONES (con $" + BET_STAKE + ")", "", "", "Cuota", "Prob", "Recibes"]);
  (B.combos.balanced.length ? B.combos.balanced : B.combos.safest).slice(0, 3).forEach(c => {
    const legs = c.legs.map(l => l.sel === "X" ? "Empate" : esName(l.name)).join(" + ");
    rows.push([clean(legs), "", "combinada", c.odd, Math.round(c.prob * 100) + "%",
               "$" + BET_STAKE + "->$" + Math.round(BET_STAKE * c.odd)]);
  });
  const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "quiniela_mundial2026.csv";
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

/* ---------- Groups ---------- */
function renderGroups() {
  const el = document.getElementById("groupsEl");
  el.innerHTML = "";
  Object.keys(DATA.groups).sort().forEach(g => {
    const rows = DATA.groups[g];
    const card = document.createElement("div");
    card.className = "group-card";
    const complete = DATA.group_complete ? DATA.group_complete[g] : true;
    let body = "";
    rows.forEach(r => {
      const cls = r.pos <= 2 ? `q${r.pos}` : (r.pos === 3 ? "q3" : "");
      body += `<tr class="${cls}">
        <td class="l"><span class="pos">${r.pos}</span> ${flag(r.team)} ${esName(r.team)}</td>
        <td>${r.P}</td><td>${r.W}-${r.D}-${r.L}</td>
        <td>${r.GF}:${r.GA}</td><td>${r.GD > 0 ? "+" + r.GD : r.GD}</td>
        <td class="pts">${r.Pts}</td></tr>`;
    });
    const badge = complete ? `<em class="gbadge done">Definido</em>`
                           : `<em class="gbadge prov">J3 por jugar</em>`;
    card.innerHTML = `<h3>Grupo <span>${g}</span> ${badge}</h3>
      <table class="standings">
        <thead><tr><th class="l">Equipo</th><th>PJ</th><th>G-E-P</th>
          <th>GF:GC</th><th>DG</th><th>Pts</th></tr></thead>
        <tbody>${body}</tbody>
      </table>`;
    el.appendChild(card);
  });
}

/* ---------- Predicciones de grupos ya jugados vs realidad ---------- */
function renderGroupPlayed() {
  const wrap = document.getElementById("groupPlayedWrap");
  const el = document.getElementById("groupPlayedEl");
  if (!BT || !BT.matches || !el) { if (wrap) wrap.style.display = "none"; return; }
  const ms = BT.matches.slice().sort((a, b) => a.date.localeCompare(b.date));
  let hit = 0, tot = 0;
  let body = "";
  ms.forEach(m => {
    const top = Math.max(m.e1, m.ex, m.e2);  // ensemble (coherente con m.pred y m.hit)
    const ok = m.hit;
    if (m.eligible) { tot++; hit += ok ? 1 : 0; }
    body += `<tr class="${ok ? "row-hit" : "row-miss"}">
      <td class="l mono">${m.date.slice(5)}</td>
      <td class="l">${flag(m.home)} ${esName(m.home)} <span class="vs">vs</span> ${flag(m.away)} ${esName(m.away)}</td>
      <td class="mono">${m.pred} ${pct(top)}</td>
      <td class="mono real">${m.real_score[0]}-${m.real_score[1]}</td>
      <td>${ok ? '<span class="ok">✓</span>' : '<span class="miss">✗</span>'}</td></tr>`;
  });
  el.innerHTML = `<thead><tr><th class="l">Fecha</th><th class="l">Partido</th>
    <th>Mi pred.</th><th>Real</th><th>✓</th></tr></thead><tbody>${body}</tbody>`;
  const h3 = document.querySelector("#groupPlayedWrap h3");
  if (h3 && tot) h3.textContent += `  —  acierto ${hit}/${tot} (${(hit / tot * 100).toFixed(0)}%)`;
}

/* ---------- Predicciones de partidos de grupo por jugar ---------- */
function renderGroupPredictions() {
  const wrap = document.getElementById("groupPredWrap");
  const el = document.getElementById("groupPredsEl");
  const preds = DATA.group_predictions || [];
  if (!preds.length) { wrap.style.display = "none"; return; }
  el.innerHTML = "";
  preds.forEach(gp => el.appendChild(groupPredCard(gp)));
}

function groupPredCard(gp) {
  const card = document.createElement("button");
  card.className = "match gp-card";
  card.type = "button";
  card.setAttribute("aria-label", `${esName(gp.teamA)} contra ${esName(gp.teamB)}, predicción`);
  const favText = gp.pred === "1" ? "Gana " + esName(gp.teamA)
                : gp.pred === "2" ? "Gana " + esName(gp.teamB) : "Empate";
  card.innerHTML = `
    <div class="mtag">Grupo ${gp.group} · ${gp.date}${gp.hasOdds ? ' · 📊 mercado' : ''}</div>
    <div class="team-row">
      ${flag(gp.teamA)}<span class="tname">${esName(gp.teamA)}</span>
      <span class="mscore">${gp.scoreA}</span>
    </div>
    <div class="team-row">
      ${flag(gp.teamB)}<span class="tname">${esName(gp.teamB)}</span>
      <span class="mscore">${gp.scoreB}</span>
    </div>
    <div class="gp-foot">${favText} · ${pct(Math.max(gp.p1, gp.px, gp.p2))}</div>`;
  card.addEventListener("click", () => { location.hash = `match-${gp.match}`; });
  return card;
}

/* ---------- Advancement ---------- */
function renderAdvancement() {
  const cols = [["Qualify", "Clasifica"], ["R16", "Octavos"], ["QF", "Cuartos"],
               ["SF", "Semis"], ["Final", "Final"], ["Champion", "Modelo"]];
  if (DATA.advancement.some(r => r.market_champ != null)) cols.push(["market_champ", "Mercado"]);
  const el = document.getElementById("advEl");
  let head = `<thead><tr><th class="l">#</th><th class="l">Selección</th>`;
  cols.forEach(c => head += `<th>${c[1]}</th>`);
  head += `</tr></thead>`;
  let body = "<tbody>";
  DATA.advancement.forEach((r, i) => {
    body += `<tr><td class="l"><span class="ranknum">${i + 1}</span></td>
      <td class="l"><div class="team-cell">${flag(r.team)} ${esName(r.team)}
        <span class="ranknum" style="margin-left:auto">${r.elo}</span></div></td>`;
    cols.forEach(c => {
      const v = r[c[0]];
      const isC = c[0] === "Champion" || c[0] === "market_champ";
      if (v == null) { body += `<td><div class="bar-cell"><span class="val">·</span></div></td>`; return; }
      body += `<td><div class="bar-cell ${isC ? "champ" : ""}">
        <div class="barbg"><div class="barfill" style="width:${(v * 100).toFixed(1)}%"></div></div>
        <span class="val">${v > 0.001 ? pct1(v) : "·"}</span></div></td>`;
    });
    body += `</tr>`;
  });
  body += "</tbody>";
  el.innerHTML = head + body;
}

/* ---------- Backtest / Validación ---------- */
function renderBacktest() {
  const mEl = document.getElementById("btMetrics");
  const tEl = document.getElementById("btTable");
  if (!BT) {
    mEl.innerHTML = `<p class="tl-empty">No hay datos de validación. Ejecuta <code>python src/backtest.py</code>.</p>`;
    return;
  }
  // Comparación multi-Mundial (si está disponible)
  const tt = BT.meta && BT.meta.tournaments;
  if (tt) {
    let rows = "";
    Object.keys(tt).sort().forEach(y => {
      const t = tt[y];
      if (!t || !t.n) return;
      const best = Math.max(t.stat_acc, t.xgb_acc, t.ens_acc);
      const cell = (v) => `<td class="${v === best ? "bt-best" : ""}">${pct1(v)}</td>`;
      rows += `<tr><td class="l">Mundial ${y}</td><td>${t.n}</td>
        ${cell(t.stat_acc)}${cell(t.xgb_acc)}${cell(t.ens_acc)}
        <td>${pct1(t.baseline_elo_acc)}</td></tr>`;
    });
    const ttHTML = `<table class="bt-compare">
      <thead><tr><th class="l">Torneo</th><th>Partidos</th><th>📊 Estadístico</th>
        <th>🤖 XGBoost</th><th>🔀 Ensemble</th><th>Baseline Elo</th></tr></thead>
      <tbody>${rows}</tbody></table>
      <p class="bt-note">Acierto 1X2 prediciendo cada partido <b>antes</b> de jugarse, con el modelo entrenado solo con datos previos a cada Mundial. (El 2022 fue históricamente caótico — muchas sorpresas.)</p>`;
    const wrap = document.createElement("div");
    wrap.innerHTML = ttHTML;
    mEl.parentNode.insertBefore(wrap, mEl);
  }

  const m = BT.metrics_eligible;
  const best = Math.max(m.stat_acc, m.xgb_acc, m.ens_acc);
  const cards = [
    ["stat", "📊 Estadístico", pct1(m.stat_acc), `LogLoss ${m.stat_logloss.toFixed(3)}`, m.stat_acc === best ? "good" : ""],
    ["xgb", "🤖 XGBoost", pct1(m.xgb_acc), `LogLoss ${m.xgb_logloss.toFixed(3)}`, m.xgb_acc === best ? "good" : ""],
    ["ens", "🔀 Ensemble", pct1(m.ens_acc), `LogLoss ${m.ens_logloss.toFixed(3)}`, m.ens_acc === best ? "good" : ""],
    ["elo", "📈 Elo", pct1(m.baseline_elo_acc), "referencia", ""],
    ...(m.y2026_acc != null ? [["y2026", "🆕 Solo 2026", pct1(m.y2026_acc), "sin histórico", ""]] : []),
    [null, "🎯 Marcador exacto", pct1(m.exact_score), `${m.n} partidos`, ""],
  ];
  mEl.innerHTML = cards.map(c => `
    <div class="mcard ${c[4]} ${c[0] ? "mc-click" : ""} ${c[0] === VALID_MODEL ? "mc-sel" : ""}" ${c[0] ? `data-model="${c[0]}"` : ""}>
      <div class="mc-val">${c[2]}</div>
      <div class="mc-lab">${c[1]}</div>
      <div class="mc-sub">${c[3]}</div>
    </div>`).join("");
  mEl.querySelectorAll(".mc-click").forEach(card =>
    card.addEventListener("click", () => {
      VALID_MODEL = card.dataset.model;
      mEl.querySelectorAll(".mcard").forEach(c => c.classList.remove("mc-sel"));
      card.classList.add("mc-sel");
      renderBtTable();
    }));
  renderBtTable();
}

function _pois(k, lam) {  // Poisson pmf
  let p = Math.exp(-lam);
  for (let i = 1; i <= k; i++) p *= lam / i;
  return p;
}
function modalScore(lh, la, outcome) {  // marcador más probable condicionado al resultado
  const RHO = -0.05, MG = 8;
  let best = [1, 0], bestp = -1;
  for (let i = 0; i <= MG; i++) for (let j = 0; j <= MG; j++) {
    if (outcome === 0 && !(i > j)) continue;
    if (outcome === 2 && !(i < j)) continue;
    if (outcome === 1 && i !== j) continue;
    let p = _pois(i, lh) * _pois(j, la);
    if (i === 0 && j === 0) p *= 1 - lh * la * RHO;
    else if (i === 0 && j === 1) p *= 1 + lh * RHO;
    else if (i === 1 && j === 0) p *= 1 + la * RHO;
    else if (i === 1 && j === 1) p *= 1 - RHO;
    if (p > bestp) { bestp = p; best = [i, j]; }
  }
  return best;
}

function renderBtTable() {
  const tEl = document.getElementById("btTable");
  if (!tEl || !BT) return;
  const pref = VMODELS[VALID_MODEL].p;
  const labels = ["1", "X", "2"];
  const elig = BT.matches.filter(x => x.eligible);
  const predOf = (x) => {
    const pv = [x[pref + "1"], x[pref + "x"], x[pref + "2"]];
    return labels[pv.indexOf(Math.max(...pv))];
  };
  // Desglose victorias vs empates para el modelo seleccionado
  const wins = elig.filter(x => x.real !== "X");
  const draws = elig.filter(x => x.real === "X");
  const hitW = wins.filter(x => predOf(x) === x.real).length;
  const hitD = draws.filter(x => predOf(x) === x.real).length;
  const nPredX = elig.filter(x => predOf(x) === "X").length;
  const sEl = document.getElementById("btSplit");
  if (sEl) {
    // --- Mercados (goles/córners con la λ del modelo; tarjetas compartida) ---
    const mk = BT.metrics_eligible && BT.metrics_eligible.markets;
    let mktHTML = "";
    if (mk) {
      const gm = mk.goals[VALID_MODEL] || mk.goals.ens;
      const cm = mk.corners[VALID_MODEL] || mk.corners.ens;
      mktHTML = `<div class="bt-split bt-mkt">
        <span class="bts-it mkt-title">📈 Mercados <small>(${gm.n} partidos)</small></span>
        <span class="bts-it">⚽ Goles O/U 2.5: <b>${pct(gm.ou_acc)}</b> <small>(±${gm.mae} gol)</small></span>
        <span class="bts-it">🚩 Córners O/U 9.5: <b>${pct(cm.ou_acc)}</b> <small>(±${cm.mae})</small></span>
        <span class="bts-it">🟨 Tarjetas O/U 3.5: <b>${pct(mk.cards.ou_acc)}</b> <small>(compartida, ±${mk.cards.mae})</small></span>
      </div>`;
    }
    sEl.innerHTML = `<div class="bt-split">
      <span class="bts-it"><b>${VMODELS[VALID_MODEL].n}</b> en ${elig.length} partidos</span>
      <span class="bts-it ok-tone">✅ Victorias: <b>${pct(hitW / wins.length)}</b> <small>(${hitW}/${wins.length})</small></span>
      <span class="bts-it warn-tone">🤝 Empates: <b>${draws.length ? pct(hitD / draws.length) : "—"}</b> <small>(${hitD}/${draws.length})</small></span>
      <span class="bts-it">Predijo empate: <b>${nPredX}</b> ${nPredX === 1 ? "vez" : "veces"}</span>
    </div>${mktHTML}`;
  }
  let head = `<thead><tr><th class="l">Fecha</th><th class="l">Partido</th>
    <th>Pred. <span class="th-mod">${VMODELS[VALID_MODEL].n}</span></th><th>Prob.</th>
    <th>Marcador</th><th>Real</th><th>Acierto</th></tr></thead>`;
  let body = "<tbody>";
  elig.forEach(x => {
    const pv = [x[pref + "1"], x[pref + "x"], x[pref + "2"]];
    const top = Math.max(...pv);
    const pi = pv.indexOf(top);
    const pred = labels[pi];
    const hit = pred === x.real;
    // marcador SIEMPRE coherente con el ganador previsto (recalculado con λ)
    const sc = (x.lh != null) ? modalScore(x.lh, x.la, pi) : x.pred_score;
    const exact = hit && sc[0] === x.real_score[0] && sc[1] === x.real_score[1];
    const mini = labels.map((k, i) =>
      `<span class="mini ${pv[i] === top ? "hot" : ""}">${k} ${pct(pv[i])}</span>`).join("");
    const status = exact ? `<span class="ok exact">Exacto</span>`
                 : hit ? `<span class="ok">✓</span>`
                 : `<span class="miss">✗</span>`;
    const cls = exact ? "row-exact" : hit ? "row-hit" : "row-miss";
    body += `<tr class="${cls}">
      <td class="l mono">${x.date.slice(5)}</td>
      <td class="l">${flag(x.home)} ${esName(x.home)} <span class="vs">vs</span> ${flag(x.away)} ${esName(x.away)}</td>
      <td class="mono">${pred}</td>
      <td class="mini-cell">${mini}</td>
      <td class="mono">${sc[0]}-${sc[1]}</td>
      <td class="mono real">${x.real_score[0]}-${x.real_score[1]}</td>
      <td>${status}</td></tr>`;
  });
  body += "</tbody>";
  tEl.innerHTML = head + body;
  renderTimingVal();
}

function renderTimingVal() {
  const el = document.getElementById("timingVal");
  if (!el || !TVAL) return;
  const mx = Math.max(...TVAL.pred, ...TVAL.real_all);
  const bars = TVAL.labels.map((lbl, i) => {
    const hp = (TVAL.pred[i] / mx) * 100, hr = (TVAL.real_all[i] / mx) * 100;
    return `<div class="tv-col">
      <div class="tv-bars">
        <div class="tv-bar pred" style="height:${hp}%" title="Predicho ${(TVAL.pred[i]*100).toFixed(1)}%"></div>
        <div class="tv-bar real" style="height:${hr}%" title="Real ${(TVAL.real_all[i]*100).toFixed(1)}%"></div>
      </div>
      <div class="tv-lab">${lbl}'</div></div>`;
  }).join("");
  el.innerHTML = `<div class="tv-card">
    <h3>⏱️ Validación de minutos de gol</h3>
    <p class="st-note">Distribución del minuto en que caen los goles: <b class="tv-k pred">predicho</b>
      (modelo entrenado solo con goles previos a 2026) vs <b class="tv-k real">real</b>
      (${TVAL.n_all.toLocaleString()} goles de Mundiales). Error medio: <b>${TVAL.mae_pts} pts</b> por tramo.</p>
    <div class="tv-chart">${bars}</div>
    <p class="st-note">✅ Captura que se anota más en la 2ª mitad y el pico final (76-90').</p>
  </div>`;
}

/* ---------- Estadísticas del torneo + rendimiento/fatiga ---------- */
function renderStats() {
  const el = document.getElementById("statsEl");
  if (!el) return;
  let html = "";
  if (STATS && STATS.categories) {
    STATS.categories.forEach(cat => {
      const rows = cat.rows.map((r, i) => `<div class="st-row">
        <span class="st-rk">${i + 1}</span>
        <span class="st-pl">${flag(r.team)} ${r.player}</span>
        <span class="st-vl">${r.value} <small>${cat.unit}</small></span></div>`).join("");
      html += `<div class="st-card"><h3>${cat.title}</h3>${rows}</div>`;
    });
  }
  if (PERF && PERF.veterans) {
    const rows = PERF.veterans.map(p => {
      const cls = p.fatigue === "alta" ? "fa-high" : (p.fatigue === "media" ? "fa-mid" : "fa-low");
      return `<div class="st-row">
        <span class="st-pl">${flag(p.team)} ${p.player} <small>(${p.age})</small></span>
        <span class="fa-tag ${cls}">${p.fatigue === "alta" ? "desgaste alto" : p.fatigue === "media" ? "desgaste medio" : "en forma"}</span></div>`;
    }).join("");
    html += `<div class="st-card st-wide"><h3>🧓 Rendimiento / fatiga de veteranos (33+)</h3>
      <p class="st-note">Por edad + tendencia goleadora (rendimiento reciente vs su pico).</p>${rows}</div>`;
  }
  if (REAL && REAL.scorers) {
    const sc = REAL.scorers.map((s, i) => `<div class="st-row">
      <span class="st-pl">${i + 1}. ${flag(s.team)} ${s.player}</span>
      <span class="st-vl">${s.goals} ⚽${s.assists ? ` · ${s.assists} 🅰️` : ""}</span></div>`).join("");
    const rf = (REAL.referees || []).map(r =>
      `<div class="st-row"><span class="st-pl">${r.referee}</span><span class="st-vl">${r.matches} partidos</span></div>`).join("");
    html += `<div class="st-card"><h3>⚽ Goleadores REALES 2026 <small>(dato en vivo)</small></h3>
      <p class="st-note">Dato real de football-data.org — alimenta el modelo bottom-up (quién anota ahora).</p>${sc}</div>`;
    html += `<div class="st-card"><h3>🧑‍⚖️ Árbitros 2026 <small>(${REAL.n_ref_matches} partidos)</small></h3>
      <p class="st-note">Árbitros reales asignados (base para severidad de tarjetas).</p>${rf}</div>`;
  }
  if (PED && PED.teams) {
    const rows = PED.teams.slice(0, 12).map(t => {
      const vets = t.top.map(v => v.player.split(" ").slice(-1)[0]).join(", ");
      return `<div class="st-row">
        <span class="st-pl">${flag(t.team)} ${esName(t.team)} <small>(${t.n} vet.)</small></span>
        <span class="st-vl">${t.xg} <small>xG hist · ${vets}</small></span></div>`;
    }).join("");
    html += `<div class="st-card st-wide"><h3>🎖️ Experiencia mundialista (StatsBomb 2018/22)</h3>
      <p class="st-note">Suma del xG en Mundiales pasados de los convocados que repiten (solo veteranos; ~8% de los planteles tiene historial).</p>${rows}</div>`;
  }
  el.innerHTML = html || `<p class="tl-empty">Sin estadísticas cargadas.</p>`;
}

/* ---------- Tabs ---------- */
function selectTab(panel) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.querySelector(`.tab[data-panel="${panel}"]`).classList.add("active");
  document.getElementById(panel).classList.add("active");
}
function setupTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => selectTab(tab.dataset.panel));
  });
}

/* ---------- Modal ---------- */
function setupModal() {
  const overlay = document.getElementById("overlay");
  overlay.addEventListener("click", e => { if (e.target === overlay) closeModal(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
}
function closeModal() {
  document.getElementById("modal").classList.remove("modal--table");
  if (location.hash) location.hash = "";
  else document.getElementById("overlay").classList.remove("open");
}

/* ---------- Tablas: clic para ampliar en un popup ---------- */
function setupTableZoom() {
  document.addEventListener("click", e => {
    const table = e.target.closest("table");
    if (!table || table.closest("#modal")) return;          // ya está dentro de un popup
    if (e.target.closest("a,button,input,select,label")) return;  // no robar clics a controles
    if (window.getSelection && String(window.getSelection()).trim()) return; // está seleccionando texto
    openTablePopup(table);
  });
}
function tablePopTitle(table) {
  const base = table.closest(".adv-wrap") || table;
  let p = base.previousElementSibling;
  while (p) { if (/^H[2-5]$/.test(p.tagName)) return p.textContent.trim(); p = p.previousElementSibling; }
  const panel = table.closest(".panel");
  const st = panel && panel.querySelector(".section-title");
  return st ? st.textContent.trim() : "Tabla";
}
function openTablePopup(table) {
  const modal = document.getElementById("modal");
  modal.classList.add("modal--table");
  modal.innerHTML =
    '<button class="close-btn" aria-label="Cerrar" onclick="closeModal()">✕</button>' +
    '<div class="table-pop"><h3 class="table-pop-title">' + tablePopTitle(table) + '</h3>' +
    '<div class="table-pop-scroll">' + table.outerHTML + '</div></div>';
  document.getElementById("overlay").classList.add("open");
}

function ouBar(label, over) {
  const o = Math.round(over * 100);          // under = 100 - over (suman 100% exacto)
  return `<div class="ou-row">
      <span class="ou-line">${label}</span>
      <div class="ou-bar">
        <div class="ou-over" style="width:${o}%">${o}%</div>
        <div class="ou-under" style="width:${100 - o}%">${100 - o}%</div>
      </div>
    </div>`;
}
function ouLegendHTML() {
  return `<div class="ou-legend"><span><i class="ou-sw over"></i>Más de (Over)</span>
      <span><i class="ou-sw under"></i>Menos de (Under)</span></div>`;
}
function overUnderHTML(mt) {
  const perM = mt.mkt && mt.mkt[TMODEL];
  const ou = perM ? perM.ou : mt.ou;
  if (!ou) return "";
  const rows = [["+1.5 goles", ou.o15], ["+2.5 goles", ou.o25], ["+3.5 goles", ou.o35]]
    .map(([l, p]) => ouBar(l, p)).join("");
  return `<div class="block">
    <p class="block-title">⚽ Goles totales — más probable: <b>${ou.mode}</b>${
      ou.exp != null ? ` <span class="exp-tag">esperado ${ou.exp.toFixed(1)}</span>` : ""}${
      perM ? ` <span class="mkt-tag">según ${VMODELS[TMODEL].n}</span>` : ""}</p>
    <div class="ou-wrap">${rows}</div>${ouLegendHTML()}
  </div>`;
}
function marketHTML(title, mkt) {
  if (!mkt || !mkt.lines) return "";
  const rows = mkt.lines.map(L => ouBar("+" + L.l, L.over)).join("");
  return `<div class="block">
    <p class="block-title">${title} — más probable: <b>${mkt.mode}</b>${
      mkt.exp != null ? ` <span class="exp-tag">esperado ${mkt.exp.toFixed(1)}</span>` : ""}</p>
    <div class="ou-wrap">${rows}</div>${ouLegendHTML()}
  </div>`;
}

function modelSelHTML() {
  return `<span class="mdl-sel">${["ens", "xgb", "stat", "elo", "y2026"].map(m =>
    `<button class="mdl-btn${m === TMODEL ? " on" : ""}" onclick="setTModel('${m}')">${VMODELS[m].n}</button>`).join("")}</span>`;
}
function modelProbBarHTML(mt) {
  if (!mt.models) return "";
  const mdl = mt.models[TMODEL] || mt.models.ens;
  const oi = mdl.indexOf(Math.max(...mdl));
  const wlbl = oi === 0 ? "Gana " + esName(mt.teamA) : oi === 2 ? "Gana " + esName(mt.teamB) : "Empate";
  return `<div class="block">
    <p class="block-title">Comparar modelos — resultado 1-X-2 en 90' ${modelSelHTML()}</p>
    <div class="prob-bar">
      <div class="prob-seg a" style="width:${mdl[0] * 100}%">${pct(mdl[0])}</div>
      <div class="prob-seg x" style="width:${mdl[1] * 100}%">${pct(mdl[1])}</div>
      <div class="prob-seg b" style="width:${mdl[2] * 100}%">${pct(mdl[2])}</div>
    </div>
    <div class="prob-meta"><span>Gana ${esName(mt.teamA)}</span><span>Empate</span><span>Gana ${esName(mt.teamB)}</span></div>
    <p class="mdl-note">Según <b>${VMODELS[TMODEL].n}</b>: ${wlbl} (${pct(Math.max(...mdl))})</p>
  </div>`;
}
function setTModel(m) { TMODEL = m; if (CURRENT_MT) openModal(CURRENT_MT); }

function openModal(mt) {
  CURRENT_MT = mt;
  const isGroup = mt.round === "group";
  // Coherencia total: ganador + marcador + chart salen del MISMO modelo elegido
  let dispPred = mt.pred, dispA = mt.scoreA, dispB = mt.scoreB, dispMdl = null;
  if (isGroup && mt.models && mt.xgA != null) {
    dispMdl = mt.models[TMODEL] || mt.models.ens;
    const oi = dispMdl.indexOf(Math.max(...dispMdl));
    dispPred = ["1", "X", "2"][oi];
    [dispA, dispB] = modalScore(mt.xgA, mt.xgB, oi);
  }
  const subhead = isGroup
      ? `Tiempo reglamentario`
      : (mt.decided === "pens" ? `Definido en penales (${mt.penA}-${mt.penB})`
        : mt.decided === "ET" ? "Definido en la prórroga" : "Tiempo reglamentario");
  const headTitle = isGroup
      ? `Grupo ${mt.group} · ${mt.date}`
      : `${ROUND_LABELS[mt.round]} · Partido ${mt.match}`;
  const resultLine = isGroup
      ? `<div style="text-align:center"><span class="winner-pill">Predicción (${VMODELS[TMODEL].n}): ${
          dispPred === "1" ? "gana " + esName(mt.teamA)
          : dispPred === "2" ? "gana " + esName(mt.teamB) : "empate"}</span></div>`
      : `<div style="text-align:center"><span class="winner-pill">▶ Avanza ${esName(mt.winner)} ${flag(mt.winner)}</span></div>`;
  const gm3 = (isGroup && dispMdl) ? dispMdl : [mt.p1, mt.px, mt.p2];
  const probBlock = isGroup ? `
      <div class="block">
        <p class="block-title">Probabilidad 1-X-2 ${modelSelHTML()}${(TMODEL === "ens" && mt.hasOdds) ? ' · 📊 incluye cuotas' : ''}</p>
        <div class="prob-bar">
          <div class="prob-seg a" style="width:${gm3[0] * 100}%">${pct(gm3[0])}</div>
          <div class="prob-seg x" style="width:${gm3[1] * 100}%">${pct(gm3[1])}</div>
          <div class="prob-seg b" style="width:${gm3[2] * 100}%">${pct(gm3[2])}</div>
        </div>
        <div class="prob-meta"><span>Gana ${esName(mt.teamA)}</span><span>Empate</span><span>Gana ${esName(mt.teamB)}</span></div>
      </div>` : `
      <div class="block">
        <p class="block-title">Probabilidad de avanzar</p>
        <div class="prob-bar">
          <div class="prob-seg a" style="width:${mt.pA * 100}%">${pct(mt.pA)}</div>
          <div class="prob-seg b" style="width:${mt.pB * 100}%">${pct(mt.pB)}</div>
        </div>
        <div class="prob-meta"><span>${esName(mt.teamA)}</span><span>${esName(mt.teamB)}</span></div>
      </div>`;

  const modal = document.getElementById("modal");
  modal.classList.remove("modal--table");
  modal.innerHTML = `
    <div class="modal-head">
      <button class="close-btn" aria-label="Cerrar" onclick="closeModal()">✕</button>
      <div class="modal-round">${headTitle}</div>
      <div class="score-board">
        <div class="sb-team">
          <div class="sflag">${flag(mt.teamA, "fl-lg")}</div>
          <div class="sname">${esName(mt.teamA)}</div>
        </div>
        <div>
          <div class="sb-score">${dispA} <span style="color:var(--muted)">·</span> ${dispB}</div>
        </div>
        <div class="sb-team">
          <div class="sflag">${flag(mt.teamB, "fl-lg")}</div>
          <div class="sname">${esName(mt.teamB)}</div>
        </div>
      </div>
      <div class="sb-decided">${subhead}</div>
      ${resultLine}
    </div>
    <div class="modal-body">
      ${probBlock}
      ${isGroup ? "" : modelProbBarHTML(mt)}

      ${overUnderHTML(mt)}

      <div class="block">
        <p class="block-title">Cómo va quedando — minutos de gol</p>
        ${timelineHTML(mt)}
      </div>

      <div class="block">
        <p class="block-title">¿En qué minuto anota cada equipo? (prob. de marcar por tramo)</p>
        ${bucketsHTML(mt)}
      </div>

      ${!isGroup && mt.resolution ? `<div class="block">
        <p class="block-title">¿Cómo se decide? (prórroga / penales)</p>
        <div class="reso-bar">
          <div class="reso-seg r-reg" style="width:${mt.resolution.regular*100}%">90'</div>
          <div class="reso-seg r-et" style="width:${mt.resolution.ET*100}%">TE</div>
          <div class="reso-seg r-pen" style="width:${mt.resolution.pens*100}%">Pen</div>
        </div>
        <div class="reso-meta">
          <span>Tiempo regular ${pct(mt.resolution.regular)}</span>
          <span>Prórroga ${pct(mt.resolution.ET)}</span>
          <span>Penales ${pct(mt.resolution.pens)}</span>
        </div>
        <p class="pen-note">Si hay penales, gana más probablemente:
          <b>${mt.penWinA >= mt.penWinB ? esName(mt.teamA) : esName(mt.teamB)}</b>
          (${pct(Math.max(mt.penWinA, mt.penWinB))}) — los penales son casi un volado.</p>
      </div>` : ""}

      ${mt.topScores ? `<div class="block">
        <p class="block-title">Marcadores más probables</p>
        ${topScoresChartHTML(mt, dispA, dispB, dispMdl)}
      </div>` : ""}

      ${mt.factors ? `<div class="block">
        <p class="block-title">¿En qué se basa la predicción?</p>
        ${factorsHTML(mt)}
      </div>` : ""}

      ${marketHTML("🟨 Tarjetas amarillas (total) · compartida", mt.cardsMkt)}

      ${marketHTML("⛳ Tiros de esquina (total) · según " + VMODELS[TMODEL].n,
        (mt.mkt && mt.mkt[TMODEL] ? mt.mkt[TMODEL].cornersMkt : mt.cornersMkt))}

      ${(mt.penShareA != null || mt.penShareB != null) ? `<div class="block">
        <p class="block-title">Dependencia del penal (% de sus goles, histórico)</p>
        <div class="cards-row">
          <div class="cards-team"><span class="pk"></span> ${mt.penShareA != null ? pct(mt.penShareA) : "—"} <span class="ct">${esName(mt.teamA)}</span></div>
          <div class="cards-team"><span class="ct">${esName(mt.teamB)}</span> ${mt.penShareB != null ? pct(mt.penShareB) : "—"} <span class="pk"></span></div>
        </div>
      </div>` : ""}

      ${(mt.scorersA || mt.scorersB) ? `<div class="block">
        <p class="block-title">Jugadores clave (goleadores y dependencia de estrella)</p>
        <div class="players-grid">
          ${playersHTML(mt.teamA, mt.scorersA)}
          ${playersHTML(mt.teamB, mt.scorersB)}
        </div>
      </div>` : ""}

      ${((mt.injuriesA && mt.injuriesA.length) || (mt.injuriesB && mt.injuriesB.length)) ? `<div class="block">
        <p class="block-title">Bajas y dudas (parte médico)</p>
        <div class="players-grid">
          ${injuriesHTML(mt.teamA, mt.injuriesA)}
          ${injuriesHTML(mt.teamB, mt.injuriesB)}
        </div>
      </div>` : ""}

      ${(mt.moraleA || mt.moraleB) ? `<div class="block">
        <p class="block-title">Ánimo / momentum (análisis de noticias · NLP)</p>
        ${moraleHTML(mt.teamA, mt.moraleA)}
        ${moraleHTML(mt.teamB, mt.moraleB)}
      </div>` : ""}
    </div>`;

  document.getElementById("overlay").classList.add("open");
}

function timelineHTML(mt) {
  if (!mt.timeline.length) {
    return `<p class="tl-empty">Marcador previsto sin goles (0-0). Probable definición ajustada.</p>`;
  }
  const maxMin = Math.max(90, ...mt.timeline.map(g => g.minute));
  let nodes = "";
  mt.timeline.forEach(g => {
    const left = Math.min(98, Math.max(2, (g.minute / maxMin) * 100));
    const top = g.team === "A" ? 28 : 72;
    const who = g.team === "A" ? mt.teamA : mt.teamB;
    nodes += `<div class="gnode" style="left:${left}%; top:${top}%" title="${esName(who)} — min ${g.minute}'">
      <span class="grun">${g.a}-${g.b}</span>
      <span class="gdot ${g.team.toLowerCase()}"></span>
      <span class="gmin">${g.minute}'</span>
    </div>`;
  });
  const halfPos = (45 / maxMin) * 100;
  return `
    <div class="timeline">
      <div class="pitch">
        <div class="mid-row"></div>
        <div class="half-line" style="left:${halfPos}%"></div>
        ${nodes}
      </div>
      <div class="axis"><span>0'</span><span>45'</span><span>${maxMin}'</span></div>
      <div class="tl-legend">
        <span><i class="gdot a" style="background:var(--primary)"></i>${esName(mt.teamA)}</span>
        <span><i class="gdot b" style="background:#a855f7"></i>${esName(mt.teamB)}</span>
      </div>
    </div>`;
}

function topScoresChartHTML(mt, predA, predB, mdl) {
  const codeA = (TEAM_CODE[mt.teamA] || "").replace("_", "") || "A";
  const codeB = (TEAM_CODE[mt.teamB] || "").replace("_", "") || "B";
  if (predA == null) { predA = mt.scoreA; predB = mt.scoreB; }
  // El ganador SIEMPRE se deriva del marcador mostrado → 100% coherente (grupos y bracket)
  const oi = predA > predB ? 0 : (predA < predB ? 2 : 1);
  const outLbl = oi === 0 ? "Gana " + esName(mt.teamA)
              : oi === 2 ? "Gana " + esName(mt.teamB) : "Empate";
  // "Como resultado": en eliminatorias usa el resultado 90' coherente (con lesiones);
  // en grupos, suma los marcadores mostrados.
  let agg;
  if (mt.outcome90) {
    agg = mt.outcome90;
  } else {
    agg = [0, 0, 0];
    mt.topScores.forEach(s => { const [i, j] = s.score; agg[i > j ? 0 : i < j ? 2 : 1] += s.p; });
  }
  // poner el marcador previsto primero, el resto por probabilidad
  const scores = mt.topScores.slice().sort((a, b) => {
    const ap = a.score[0] === predA && a.score[1] === predB ? 1 : 0;
    const bp = b.score[0] === predA && b.score[1] === predB ? 1 : 0;
    return bp - ap || b.p - a.p;
  });
  const maxp = Math.max(...scores.map(s => s.p));
  const rows = scores.map(s => {
    const [i, j] = s.score;
    const cls = i > j ? "win-a" : (i < j ? "win-b" : "win-d");
    const w = (s.p / maxp * 100).toFixed(0);
    const isPred = i === predA && j === predB;
    return `<div class="tsb-row${isPred ? " tsb-pred" : ""}">
      <span class="tsb-label">${codeA} <b>${i}-${j}</b> ${codeB}${isPred ? ' <span class="tsb-star">★ previsto</span>' : ""}</span>
      <div class="tsb-track"><div class="tsb-fill ${cls}" style="width:${w}%"></div></div>
      <span class="tsb-pct">${(s.p * 100).toFixed(1)}%</span>
    </div>`;
  }).join("");
  return `<div class="ts-head">Resultado más probable: <b>${outLbl}</b> · marcador <b>${predA}-${predB}</b></div>
    <div class="ts-chart">${rows}</div>
    <p class="ts-note">Como <b>resultado</b>: ${esName(mt.teamA)} ${(agg[0]*100).toFixed(0)}% · empate ${(agg[1]*100).toFixed(0)}% · ${esName(mt.teamB)} ${(agg[2]*100).toFixed(0)}%. (Un empate puede ser el <i>marcador suelto</i> más común aunque la <b>suma</b> de victorias sea mayor — por eso el ganador y el marcador concuerdan.)</p>
    <div class="ts-legend">
      <span><i class="sw win-a"></i>Gana ${esName(mt.teamA)}</span>
      <span><i class="sw win-d"></i>Empate</span>
      <span><i class="sw win-b"></i>Gana ${esName(mt.teamB)}</span>
    </div>`;
}

function moraleHTML(team, m) {
  if (!m) return "";
  const s = m.score;
  const cls = s >= 0.3 ? "mo-pos" : (s <= -0.2 ? "mo-neg" : "mo-neu");
  const pctW = ((s + 1) / 2 * 100).toFixed(0);
  const label = s >= 0.3 ? "Alto" : (s <= -0.2 ? "Bajo" : "Neutro");
  return `<div class="mo-row">
    <div class="mo-top"><span>${flag(team)} ${esName(team)}</span>
      <span class="mo-val ${cls}">${label} (${s > 0 ? "+" : ""}${s.toFixed(1)})</span></div>
    <div class="mo-track"><div class="mo-fill ${cls}" style="width:${pctW}%"></div></div>
    <div class="mo-note">${m.note}</div>
  </div>`;
}

function injuriesHTML(team, inj) {
  if (!inj || !inj.length) {
    return `<div class="pl-team"><div class="pl-head">${flag(team)} ${esName(team)}</div>
      <div class="pl-empty">sin bajas reportadas</div></div>`;
  }
  const rows = inj.map(p => {
    const out = p.status === "out";
    return `<div class="pl-row">
      <span class="pl-name">${p.player}</span>
      <span class="inj-tag ${out ? "inj-out" : "inj-doubt"}">${out ? "BAJA" : "duda"}</span></div>
      <div class="inj-detail">${p.injury}</div>`;
  }).join("");
  return `<div class="pl-team"><div class="pl-head">${flag(team)} ${esName(team)}</div>${rows}</div>`;
}

function playersHTML(team, sc) {
  if (!sc || !sc.top || !sc.top.length) {
    return `<div class="pl-team"><div class="pl-head">${flag(team)} ${esName(team)}</div>
      <div class="pl-empty">sin datos de goleadores</div></div>`;
  }
  const dep = sc.star_dependency;
  const depCls = dep >= 0.4 ? "dep-high" : (dep >= 0.28 ? "dep-mid" : "dep-low");
  const rows = sc.top.map(p =>
    `<div class="pl-row"><span class="pl-name">${p.name}</span>
      <span class="pl-goals">${p.recent}${p.wc ? ` <b>·${p.wc} en MD</b>` : ""}</span></div>`).join("");
  return `<div class="pl-team">
    <div class="pl-head">${flag(team)} ${esName(team)}</div>
    ${rows}
    <div class="pl-dep ${depCls}">Dependencia de estrella: ${pct(dep)}</div>
  </div>`;
}

function factorsHTML(mt) {
  const f = mt.factors;
  const fav = mt.winner || (mt.pred === "1" ? mt.teamA : mt.pred === "2" ? mt.teamB : null);
  const reasons = [];
  if (f.eloA !== f.eloB) {
    const strong = f.eloA > f.eloB ? mt.teamA : mt.teamB;
    reasons.push(`mayor Elo (${esName(strong)}: ${Math.max(f.eloA, f.eloB)} vs ${Math.min(f.eloA, f.eloB)})`);
  }
  if (Math.abs(f.formA - f.formB) >= 0.3) {
    const better = f.formA > f.formB ? mt.teamA : mt.teamB;
    reasons.push(`mejor forma reciente (${esName(better)})`);
  }
  if (f.xgA != null && f.xgB != null && Math.abs(f.xgA - f.xgB) >= 0.15) {
    const better = f.xgA > f.xgB ? mt.teamA : mt.teamB;
    reasons.push(`mayor xG (${esName(better)})`);
  }
  if (f.market) reasons.push("cuotas del mercado");
  const row = (name, elo, form, xg) => `<tr>
    <td class="l">${esName(name)}</td><td>${elo}</td><td>${form}</td>
    <td>${xg != null ? xg : "—"}</td></tr>`;
  return `
    <table class="factors">
      <thead><tr><th class="l">Equipo</th><th>Elo</th><th>Forma (pts/p)</th><th>xG</th></tr></thead>
      <tbody>${row(mt.teamA, f.eloA, f.formA, f.xgA)}${row(mt.teamB, f.eloB, f.formB, f.xgB)}</tbody>
    </table>
    ${fav ? `<p class="why">Se inclina por <b>${esName(fav)}</b> por: ${reasons.join(", ") || "muy parejo"}.</p>` : ""}`;
}

function bucketsHTML(mt) {
  const labels = ["1-15", "16-30", "31-45", "46-60", "61-75", "76-90"];
  const heat = (v, hue) => {
    const a = 0.12 + v * 0.85;
    return `background: hsla(${hue}, 80%, 55%, ${a.toFixed(2)})`;
  };
  let head = `<div class="blab"></div>`;
  labels.forEach(l => head += `<div class="bh">${l}'</div>`);
  let rowA = `<div class="blab">${flag(mt.teamA)} ${esName(mt.teamA)}</div>`;
  labels.forEach(l => rowA += `<div class="bcell" style="${heat(mt.bucketsA[l], 217)}">${pct(mt.bucketsA[l])}</div>`);
  let rowB = `<div class="blab">${flag(mt.teamB)} ${esName(mt.teamB)}</div>`;
  labels.forEach(l => rowB += `<div class="bcell" style="${heat(mt.bucketsB[l], 270)}">${pct(mt.bucketsB[l])}</div>`);
  return `<div class="buckets">${head}${rowA}${rowB}</div>`;
}
