// @ts-nocheck
// Leveling map and heat grid, ported from prototypes/bid-landscape/index.html (see docs/bid-landscape-visualization.md).
// The drawing code is kept as it was verified there; clicks, hovers and selection are handed to the app through `app`.
var SVGNS = 'http://www.w3.org/2000/svg';
var state = { sel: null, cell: null, openItem: null, notes: 'on', rowMode: 'equal' };
var app = { onCell: function () {}, onBidder: function () {}, cellTip: function () {}, bidderTip: function () {}, rowTip: function () {}, hideTip: function () {}, rerender: function () {} };
export function configure(s, a) { Object.assign(state, s); Object.assign(app, a); }
export function viewState() { return state; }
function el(tag, attrs, parent, text) {
  var e = document.createElementNS(SVGNS, tag);
  for (var k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
  if (text != null) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}
function h(tag, cls2, parent, text) { var e = document.createElement(tag); if (cls2) e.className = cls2; if (text != null) e.textContent = text; if (parent) parent.appendChild(e); return e; }
function money(v) { return '$' + Math.round(v).toLocaleString('en-US'); }
function short(v) { var a = Math.abs(v); return (v < 0 ? '-' : '') + '$' + (a >= 1e6 ? (a / 1e6).toFixed(2) + 'M' : a >= 1e4 ? Math.round(a / 1e3) + 'k' : a >= 1e3 ? (a / 1e3).toFixed(1) + 'k' : Math.round(a)); }
function pct(d) { return (d >= 0 ? '+' : '') + Math.round(d * 100) + '%'; }
function trunc(s, n) { return s.length > n ? s.slice(0, Math.max(1, n - 1)) + '…' : s; }
function topRound(x, y, w, hh, r) { r = Math.min(r, w / 2, hh); return 'M' + x + ',' + (y + hh) + 'V' + (y + r) + 'Q' + x + ',' + y + ' ' + (x + r) + ',' + y + 'H' + (x + w - r) + 'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) + 'V' + (y + hh) + 'Z'; }
function niceTicks(max, n) { var raw = max / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), step = [1, 2, 2.5, 5, 10].map(function (m) { return m * mag; }).filter(function (s) { return s >= raw; })[0], out = []; for (var v = 0; v <= max; v += step) out.push(v); return out; }

// ---------------------------------------------------------------- A. heat grid
function miniLane(svg, M, i, x0, x1, cy) {
  var r = M.rows[i], lo = Math.log(0.3), hi = Math.log(3.3);
  var xr = function (ratio) { return x0 + (Math.max(lo, Math.min(hi, Math.log(ratio))) - lo) / (hi - lo) * (x1 - x0); };
  var refLab = r.refName.replace('the ', '');
  [[0.5, '-50%'], [1, refLab], [2, '+100%'], [3, '+200%']].forEach(function (t) {
    el('line', { x1: xr(t[0]), x2: xr(t[0]), y1: cy - 22, y2: cy + 22, stroke: t[0] === 1 ? 'var(--axis)' : 'var(--grid)' }, svg);
    el('text', { x: xr(t[0]), y: cy - 28, 'text-anchor': 'middle', 'font-size': 10, 'font-weight': t[0] === 1 ? 700 : 400, style: 'fill:var(--' + (t[0] === 1 ? 'ink' : 'muted') + ')' }, svg, t[1]);
  });
  if (r.n >= 3) el('rect', { x: xr(r.q1 / r.ref), y: cy - 13, width: Math.max(1, xr(r.q3 / r.ref) - xr(r.q1 / r.ref)), height: 26, style: 'fill:var(--surface)' }, svg);
  var dots = [];
  M.bidders.forEach(function (b) {
    var c = b.cells[i]; if (c.v == null) return; var x = xr(c.v / r.ref);
    if (c.st === 'plug') el('path', { d: 'M' + x + ',' + (cy - 4.5) + 'l4.5,4.5l-4.5,4.5l-4.5,-4.5Z', fill: 'var(--surface)', stroke: 'var(--plug-ink)', 'stroke-width': 1.5, opacity: b.qualified ? 1 : .5 }, svg);
    else if (b.qualified) dots.push([x, b]);
    else el('line', { x1: x, x2: x, y1: cy - 8, y2: cy + 8, 'stroke-width': 2, 'stroke-linecap': 'round', 'class': 's' + c.cls, opacity: .45 }, svg);
  });
  dots.forEach(function (d) { el('circle', { cx: d[0], cy: cy, r: M.rec && d[1].id === M.rec.id ? 6 : 4.5, style: 'fill:var(--ink)', stroke: 'var(--surface-2)', 'stroke-width': 2 }, svg); });
  var gx = xr(r.est / r.ref); el('path', { d: 'M' + gx + ',' + (cy + 15) + 'l4.5,7h-9Z', style: 'fill:var(--ink)' }, svg);
  el('text', { x: x0, y: cy + 38, 'font-size': 10, style: 'fill:var(--muted)' }, svg, 'Dots: qualified bidders. Ticks: the rest. Diamond: plug. Triangle: GC estimate.');
}
function drawHeat(M, host, hooks) {
  hooks = hooks || {};
  var W = host.clientWidth, N = M.order.length, items = M.items, narrow = W < 640;
  var nQ = M.order.filter(function (b) { return b.qualified; }).length, grouped = M.grouped && nQ > 0 && nQ < N, gGap = grouped ? 18 : 0;
  var left = narrow ? 108 : 214, spreadW = narrow ? 0 : 176, notesW = !narrow && W >= 1100 && state.notes === 'on' ? 244 : 0, right = spreadW + notesW;
  var cw = Math.max(9, Math.min(104, (W - left - right - 4 - gGap) / N)), gap = cw >= 14 ? 2 : 1, gridW = cw * N + gGap;
  var X = function (j) { return left + j * cw + (grouped && j >= nQ ? gGap : 0); };
  var top = 54, barsH = 92, headH = cw >= 70 ? 36 : cw >= 13 ? 22 : 8, y0 = top + barsH + headH + 8;
  var dense = items.length > 20, base = dense ? 15 : 24, secH = 22, minH = dense ? 4 : 6, totalH = base * items.length;
  var hs = items.map(function (it, i) { return state.rowMode === 'weight' ? minH + (totalH - minH * items.length) * M.weights[i] : base; });
  var open = state.openItem != null && state.openItem < items.length ? state.openItem : null, bandH = narrow ? 276 : 160, bandY = 0;
  var ys = [], y = y0, secY = [];
  M.sc.sections.forEach(function (s) { secY.push(y); y += secH; for (var i = s.first; i < s.first + s.count; i++) { ys[i] = y; y += hs[i]; if (i === open) { bandY = y + 4; y += bandH + 10; } } y += 4; });
  var svgW = Math.max(W, left + gridW + right), svgH = y + 8;
  var svg = el('svg', { width: svgW, height: svgH, viewBox: '0 0 ' + svgW + ' ' + svgH, role: 'img', 'aria-label': 'Heat grid of ' + N + ' bidders by ' + items.length + ' scope items, ' + nQ + ' qualified' }, host);

  // who qualified: group header when grouped, otherwise a one-line count
  if (grouped) {
    el('line', { x1: X(0), x2: X(nQ - 1) + cw, y1: 21, y2: 21, stroke: 'var(--ink)', 'stroke-width': 2.5 }, svg);
    el('text', { x: X(nQ - 1) + cw, y: 13, 'text-anchor': 'end', 'font-size': 12, 'font-weight': 700, style: 'fill:var(--ink)' }, svg, 'Qualified · ' + nQ);
    el('line', { x1: X(nQ), x2: X(N - 1) + cw, y1: 21, y2: 21, stroke: 'var(--axis)', 'stroke-width': 2.5 }, svg);
    el('text', { x: X(nQ), y: 13, 'font-size': 12, style: 'fill:var(--muted)' }, svg, (narrow ? 'Not qualified · ' : 'Did not qualify · ') + (N - nQ));
  } else el('text', { x: left, y: 13, 'font-size': 12, 'font-weight': 700, style: 'fill:var(--ink)' }, svg, nQ === N ? 'All ' + N + ' qualified' : nQ + ' of ' + N + ' qualified' + (nQ ? ' (marked ✓, drawn solid)' : ''));

  // margin bars: leveled total split into priced scope and plugs
  var maxV = Math.max(M.maxLev, M.estTotal) * 1.04, yb = function (v) { return top + barsH - v / maxV * barsH; };
  el('line', { x1: left, x2: left + gridW, y1: top + barsH, y2: top + barsH, stroke: 'var(--axis)' }, svg);
  el('line', { x1: left, x2: left + gridW, y1: yb(M.estTotal), y2: yb(M.estTotal), stroke: 'var(--muted)', 'stroke-width': 1 }, svg);
  el('text', { x: left - 8, y: yb(M.estTotal) + 4, 'text-anchor': 'end', 'font-size': 11 }, svg, 'GC estimate ' + short(M.estTotal));
  el('text', { x: left - 8, y: top + barsH + 1, 'text-anchor': 'end', 'font-size': 11, style: 'fill:var(--muted)' }, svg, 'Leveled total');
  var bw = Math.max(3, Math.min(24, cw - gap - 2));
  M.order.forEach(function (b, j) {
    var cx = X(j) + cw / 2, g = el('g', { 'class': b.qualified ? '' : 'faded' }, svg), priced = b.lev - b.plugs, d = topRound(cx - bw / 2, yb(priced), bw, yb(0) - yb(priced), b.plugs > 0 ? 0 : 3);
    if (b.qualified) el('path', { d: d, style: 'fill:var(--ink-2)' }, g);
    else el('path', { d: d, fill: 'none', stroke: 'var(--ink-2)', 'stroke-width': 1.3 }, g);
    if (b.plugs > 0) { var ph = yb(priced) - yb(b.lev) - 2; if (ph > 1) el('path', { d: topRound(cx - bw / 2, yb(b.lev), bw, ph, 3), 'class': 'plug' }, g); }
    el('line', { x1: cx - bw / 2 - 2, x2: cx + bw / 2 + 2, y1: yb(b.asbid), y2: yb(b.asbid), stroke: 'var(--ink)', 'stroke-width': 1.5 }, g);
    if (cw >= 44) el('text', { x: cx, y: yb(b.lev) - 5, 'text-anchor': 'middle', 'font-size': 10.5, 'font-weight': b.qualified ? 700 : 400, style: 'font-variant-numeric:tabular-nums;fill:var(--' + (b.qualified ? 'ink' : 'muted') + ')' }, svg, short(b.lev));
    if (b.qualified) {
      var mark = M.rec && b.id === M.rec.id ? '★' : '✓';
      if (cw >= 11 || mark === '★') el('text', { x: cx, y: 40, 'text-anchor': 'middle', 'font-size': mark === '★' ? 14 : 12, 'font-weight': 700, style: 'fill:var(--ink)' }, svg, mark);
      else el('circle', { cx: cx, cy: 36, r: 2.2, style: 'fill:var(--ink)' }, svg);
    }
    var lab = b.qualified ? 'fill:var(--ink)' : 'fill:var(--muted)';
    if (cw >= 22) el('text', { x: cx, y: top + barsH + 15, 'text-anchor': 'middle', 'font-size': 10.5, 'font-weight': b.qualified ? 700 : 400, style: lab }, svg, b.code);
    else if (cw >= 13 && (j === 0 || (j + 1) % 5 === 0)) el('text', { x: cx, y: top + barsH + 15, 'text-anchor': 'middle', 'font-size': 10, style: 'fill:var(--muted)' }, svg, String(j + 1));
    if (cw >= 70) el('text', { x: cx, y: top + barsH + 29, 'text-anchor': 'middle', 'font-size': 10.5, style: lab }, svg, trunc(b.name, Math.floor(cw / 5.9)));
    el('rect', { x: X(j), y: 24, width: cw, height: top + barsH + headH - 24, fill: 'transparent', 'data-bar': j, style: 'cursor:pointer' }, svg);
  });

  // rows: section headers, item labels (click to open the scope item analysis)
  var chars = Math.floor((left - 28) / 6.3);
  M.sc.sections.forEach(function (s, si) {
    el('text', { x: 0, y: secY[si] + 15, 'font-size': 11, 'font-weight': 700, style: 'fill:var(--ink);letter-spacing:.04em;text-transform:uppercase' }, svg, trunc(s.name, chars + 6));
    el('line', { x1: 0, x2: left + gridW, y1: secY[si] + 20.5, y2: secY[si] + 20.5, stroke: 'var(--grid)' }, svg);
  });
  items.forEach(function (it, i) {
    var cy = ys[i] + hs[i] / 2;
    if (hs[i] >= 10) {
      el('text', { x: 0, y: cy + 4, 'font-size': 11, style: 'fill:var(--muted)' }, svg, i === open ? '▾' : '▸');
      el('text', { x: left - 10, y: cy + 4, 'text-anchor': 'end', 'font-size': hs[i] >= 18 ? 12 : 10.5, 'font-weight': i === open ? 700 : 400, style: i === open ? 'fill:var(--ink)' : null }, svg, trunc(it.name, chars));
    }
    el('rect', { x: 0, y: ys[i], width: left - 4, height: hs[i], fill: 'transparent', 'data-row': i, style: 'cursor:pointer' }, svg);
  });
  // cells: qualified bidders get full solid cells; the rest are faded, and shrink to half height when there is no room for a number
  var cellsG = el('g', {}, svg), focus = null;
  M.order.forEach(function (b, j) {
    var x = X(j) + gap / 2, w = cw - gap, nq = !b.qualified;
    b.cells.forEach(function (c, i) {
      var yy = ys[i] + gap / 2, hh = Math.max(1, hs[i] - gap), text = w >= 52 && hh >= 16 && c.v != null;
      var inset = nq && !(w >= 52 && hh >= 16) && hh >= 6, ry = yy, rh2 = hh;
      if (inset) { rh2 = Math.max(3, hh * 0.46); ry = yy + (hh - rh2) / 2; }
      var plain = nq || c.st === 'plug' || c.st === 'incl';
      var kind = (c.st === 'plug' ? 'plug' : c.st === 'incl' ? 'incl' : 'd' + c.cls) + (nq ? ' nq' : '');
      var r = el('rect', { x: x, y: ry, width: w, height: rh2, rx: w >= 10 && rh2 >= 8 ? 2 : 0, 'class': kind }, cellsG);
      if (inset) { r.setAttribute('pointer-events', 'none'); r = el('rect', { x: x, y: yy, width: w, height: hh, fill: 'transparent' }, cellsG); }
      r.setAttribute('data-b', j); r.setAttribute('data-i', i); r.style.cursor = 'pointer';
      if (c.st === 'incl' && w >= 12 && hh >= 9) el('line', { x1: x + w / 2 - 3, x2: x + w / 2 + 3, y1: yy + hh / 2, y2: yy + hh / 2, stroke: 'var(--muted)', 'stroke-width': 1.5, 'pointer-events': 'none' }, cellsG);
      if (c.st === 'adj' && !inset && w >= 9 && hh >= 8) { var q = Math.min(6, w / 2.4, hh / 2); el('path', { d: 'M' + (x + w - q) + ',' + yy + 'H' + (x + w) + 'V' + (yy + q) + 'Z', 'class': nq ? '' : 't' + c.cls, style: nq ? 'fill:var(--ink-2)' : null, 'pointer-events': 'none', opacity: .85 }, cellsG); }
      if (c.unit && !inset && w >= 9 && hh >= 8) { var q2 = Math.min(6, w / 2.4, hh / 2); el('path', { d: 'M' + x + ',' + yy + 'H' + (x + q2) + 'L' + x + ',' + (yy + q2) + 'Z', 'class': nq ? '' : 't' + c.cls, style: nq ? 'fill:var(--ink-2)' : null, 'pointer-events': 'none', opacity: .85 }, cellsG); }
      // the analysis flagged something to check on this data point
      if (c.note.flag && hh >= 5) el('circle', { cx: w >= 30 ? x + 7 : x + w / 2, cy: ry + rh2 / 2, r: w >= 12 && rh2 >= 8 ? 2.4 : 1.7, 'class': plain ? '' : 't' + c.cls, style: plain ? 'fill:var(--ink)' : null,
        stroke: c.st === 'plug' ? 'var(--plug-bg)' : null, 'stroke-width': c.st === 'plug' ? 1.2 : null, 'pointer-events': 'none' }, cellsG);
      if (text) el('text', { x: x + w - 6, y: yy + hh / 2 + 4, 'text-anchor': 'end', 'font-size': 11, 'font-weight': nq ? 400 : 600, 'class': nq || c.st === 'plug' ? '' : 't' + c.cls,
        style: 'font-variant-numeric:tabular-nums' + (c.st === 'plug' && !nq ? ';fill:var(--ink);paint-order:stroke;stroke:var(--plug-bg);stroke-width:3px' : nq ? ';fill:var(--ink-2)' : ''), 'pointer-events': 'none' }, cellsG, short(c.v));
      if (state.cell && state.cell.id === b.id && state.cell.i === i) focus = [x, yy, w, hh];
    });
  });
  if (grouped) el('rect', { x: X(0) - 3.5, y: 27, width: nQ * cw + 7, height: svgH - 30, rx: 6, fill: 'none', stroke: 'var(--ink)', 'stroke-width': 1.5, 'pointer-events': 'none' }, svg);

  // spread column
  if (spreadW) {
    var rx0 = left + gridW + 20, rw = spreadW - 40, lo = Math.log(0.4), hi = Math.log(2.5);
    var xs = function (ratio) { return rx0 + (Math.max(lo, Math.min(hi, Math.log(ratio))) - lo) / (hi - lo) * rw; };
    el('text', { x: rx0, y: top + barsH + 15, 'font-size': 10.5, 'font-weight': 700, style: 'fill:var(--ink)' }, svg, 'Spread across bidders');
    [[0.5, '-50%'], [1, 'ref'], [2, '+100%']].forEach(function (t) { el('text', { x: xs(t[0]), y: y0 + 13, 'text-anchor': 'middle', 'font-size': 10, style: 'fill:var(--muted)' }, svg, t[1]); });
    M.rows.forEach(function (r, i) {
      var cy = ys[i] + hs[i] / 2;
      el('line', { x1: xs(1), x2: xs(1), y1: ys[i], y2: ys[i] + hs[i], stroke: 'var(--axis)' }, svg);
      if (r.n) {
        el('line', { x1: xs(r.min / r.ref), x2: xs(r.max / r.ref), y1: cy, y2: cy, stroke: 'var(--muted)' }, svg);
        var bh = Math.max(2, Math.min(8, hs[i] - 4));
        el('rect', { x: xs(r.q1 / r.ref), y: cy - bh / 2, width: Math.max(1.5, xs(r.q3 / r.ref) - xs(r.q1 / r.ref)), height: bh, style: 'fill:var(--priced)' }, svg);
        el('line', { x1: xs(r.med / r.ref), x2: xs(r.med / r.ref), y1: cy - bh / 2 - 1.5, y2: cy + bh / 2 + 1.5, stroke: 'var(--ink)', 'stroke-width': 1.5 }, svg);
      }
      if (hs[i] >= 9) { var gx = xs(r.est / r.ref); el('path', { d: 'M' + gx + ',' + (cy - 4) + 'l4,4l-4,4l-4,-4Z', fill: 'var(--surface)', stroke: 'var(--ink)', 'stroke-width': 1.1 }, svg); }
    });
  }
  // one-line scope item analysis beside each row
  if (notesW) {
    var nx = left + gridW + spreadW + 4, nchars = Math.floor((notesW - 20) / 5.6);
    el('text', { x: nx + 12, y: top + barsH + 15, 'font-size': 10.5, 'font-weight': 700, style: 'fill:var(--ink)' }, svg, 'Scope item analysis');
    M.rows.forEach(function (r, i) {
      if (hs[i] < 11) return; var cy = ys[i] + hs[i] / 2;
      if (r.note.flag) el('circle', { cx: nx + 4, cy: cy, r: 2.6, style: 'fill:var(--accent)' }, svg);
      el('text', { x: nx + 12, y: cy + 4, 'font-size': hs[i] >= 18 ? 11 : 10, 'data-row': i, style: 'cursor:pointer;fill:var(--ink-2)' }, svg, trunc(r.note.headline, nchars));
    });
  }
  // opened scope item: full analysis and every bid for the item on one line
  if (open != null) {
    el('rect', { x: 0, y: bandY, width: svgW, height: bandH, rx: 8, style: 'fill:var(--surface-2)' }, svg);
    var textW = narrow ? svgW - 24 : Math.min(600, svgW * 0.5), textH = narrow ? 168 : bandH - 16;
    var fo = el('foreignObject', { x: 12, y: bandY + 8, width: textW, height: textH }, svg), div = document.createElement('div');
    div.className = 'fo'; h('div', 'fo-t', div, items[open].name + ': scope item analysis'); h('p', '', div, M.rows[open].note.full); fo.appendChild(div);
    miniLane(svg, M, open, narrow ? 24 : 12 + textW + 40, svgW - 28, narrow ? bandY + 8 + textH + 44 : bandY + bandH / 2 + 4);
  }
  // selection frame, focused data point, linked column highlight, hover outline
  var selJ = M.order.findIndex(function (b) { return b.id === state.sel; });
  if (selJ >= 0) el('rect', { x: X(selJ) + 1, y: 28.5, width: cw - 2, height: svgH - 33, rx: 3, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2, 'pointer-events': 'none' }, svg);
  if (focus) el('rect', { x: focus[0] - 1.5, y: focus[1] - 1.5, width: focus[2] + 3, height: focus[3] + 3, rx: 3, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 3, 'pointer-events': 'none' }, svg);
  var colHL = el('rect', { y: 28.5, width: cw, height: svgH - 33, rx: 3, style: 'fill:var(--ink)', 'fill-opacity': .07, stroke: 'var(--ink)', 'stroke-width': 1, 'pointer-events': 'none', visibility: 'hidden' }, svg);
  var hov = el('rect', { fill: 'none', stroke: 'var(--ink)', 'stroke-width': 1.5, 'pointer-events': 'none', visibility: 'hidden' }, svg), lastId = null;
  function tell(id) { if (id !== lastId) { lastId = id; if (hooks.onHover) hooks.onHover(id); } }
  svg.addEventListener('pointermove', function (ev) {
    var t = ev.target, d = t.dataset || {};
    if (d.i != null) { var b = M.order[+d.b]; ['x', 'y', 'width', 'height'].forEach(function (a) { hov.setAttribute(a, t.getAttribute(a)); }); hov.setAttribute('visibility', 'visible'); app.cellTip(ev, b.id, M.items[+d.i].key); tell(b.id); }
    else if (d.bar != null) { hov.setAttribute('visibility', 'hidden'); app.bidderTip(ev, M.order[+d.bar].id); tell(M.order[+d.bar].id); }
    else if (d.row != null) { hov.setAttribute('visibility', 'hidden'); app.rowTip(ev, M.items[+d.row].key); tell(null); }
    else { hov.setAttribute('visibility', 'hidden'); app.hideTip(); tell(null); }
  });
  svg.addEventListener('pointerleave', function () { hov.setAttribute('visibility', 'hidden'); app.hideTip(); tell(null); });
  svg.addEventListener('click', function (ev) {
    var d = ev.target.dataset || {};
    if (d.row != null) { state.openItem = state.openItem === +d.row ? null : +d.row; app.rerender(); }
    else if (d.i != null) { app.onCell(M.order[+d.b].id, M.items[+d.i].key); }
    else if (d.bar != null) app.onBidder(M.order[+d.bar].id);
  });
  return { highlight: function (id) {
    var j = M.order.findIndex(function (b) { return b.id === id; });
    if (j < 0) { colHL.setAttribute('visibility', 'hidden'); return; }
    colHL.setAttribute('x', X(j)); colHL.setAttribute('visibility', 'visible');
  } };
}


// ---------------------------------------------------------------- E. leveling map
function drawMap(M, host, opt) {
  opt = opt || {};
  var W = host.clientWidth, bids = M.bidders, N = bids.length, compact = !!opt.compact;
  var left = 58, right = 26, top = 34, plotH = compact ? 262 : 360, bottom = 46, plotW = W - left - right, laneH = compact ? 64 : 74, laneY = top + laneH / 2;
  var svgH = top + plotH + bottom, svg = el('svg', { width: W, height: svgH, viewBox: '0 0 ' + W + ' ' + svgH, role: 'img', 'aria-label': 'Total price against scope completeness for ' + N + ' bidders' }, host);
  var xsAll = bids.reduce(function (a, b) { return a.concat([b.asbid, b.lev]); }, [M.estTotal]);
  var xmin = Math.min.apply(null, xsAll) * .92, xmax = Math.max.apply(null, xsAll) * 1.04;
  var covMin = Math.min.apply(null, bids.map(function (b) { return b.cov; }).concat([1])), ymin = Math.min(.8, Math.floor(covMin * 10) / 10);
  var X = function (v) { return left + (v - xmin) / (xmax - xmin) * plotW; }, Y = function (c) { return top + laneH + 16 + (1 - c) / (1 - ymin) * (plotH - laneH - 16); };
  niceTicks(xmax, W < 640 ? 4 : 7).filter(function (t) { return t >= xmin; }).forEach(function (t) {
    el('line', { x1: X(t), x2: X(t), y1: top, y2: top + plotH, stroke: 'var(--grid)' }, svg);
    el('text', { x: X(t), y: top + plotH + 16, 'text-anchor': 'middle', 'font-size': 10.5, style: 'fill:var(--muted);font-variant-numeric:tabular-nums' }, svg, short(t).replace('.00M', 'M'));
  });
  el('rect', { x: left, y: top, width: plotW, height: laneH, style: 'fill:var(--surface-2)', opacity: .55 }, svg);
  el('text', { x: left - 8, y: laneY + 4, 'text-anchor': 'end', 'font-size': 10.5, 'font-weight': 700, style: 'fill:var(--ink)' }, svg, '100%');
  var step = (1 - ymin) > .45 ? .2 : .1;
  for (var c = 1 - step; c >= ymin - 1e-9; c -= step) {
    if (!M.covMin || Math.abs(c - M.covMin) > 0.001) el('line', { x1: left, x2: left + plotW, y1: Y(c), y2: Y(c), stroke: 'var(--grid)' }, svg);
    el('text', { x: left - 8, y: Y(c) + 4, 'text-anchor': 'end', 'font-size': 10.5, style: 'fill:var(--muted)' }, svg, Math.round(c * 100) + '%');
  }
  if (M.covMin && M.covMin > ymin) {
  // the policy line: below it a bidder cannot qualify
  el('line', { x1: left, x2: left + plotW, y1: Y(M.covMin), y2: Y(M.covMin), stroke: 'var(--ink-2)', 'stroke-width': 1.25 }, svg);
  el('text', { x: left + plotW - 4, y: Y(M.covMin) + 13, 'text-anchor': 'end', 'font-size': 10.5, style: 'fill:var(--ink-2)' }, svg, 'Below this line: under ' + Math.round(M.covMin * 100) + '% of scope priced, cannot qualify');
  }
  el('text', { x: left + plotW / 2, y: svgH - 8, 'text-anchor': 'middle', 'font-size': 11 }, svg, W < 640 ? 'Tick = as bid, circle = leveled, filled = qualified' : 'Total: tick = as bid, circle = leveled. Filled circle = qualified, hollow = did not qualify.');
  el('text', { x: 0, y: 14, 'font-size': 11 }, svg, 'Scope priced by the bidder');
  el('line', { x1: X(M.estTotal), x2: X(M.estTotal), y1: top - 3, y2: top + plotH, stroke: 'var(--muted)' }, svg);
  el('text', { x: X(M.estTotal), y: top - 7, 'text-anchor': 'middle', 'font-size': 10.5 }, svg, 'GC estimate');
  el('text', { x: left + 6, y: top + 12, 'font-size': 10.5, style: 'fill:var(--muted)' }, svg, 'Priced every item');
  var pts = [], placed = [], OFF = compact ? [0, -13, 13, -25, 25] : [0, -12, 12, -24, 24, -32, 32];
  var nQ = bids.filter(function (b) { return b.qualified; }).length;
  var lowAs = bids.slice().sort(function (a, b) { return a.asbid - b.asbid; })[0];
  // not-qualified first so qualified bidders are drawn on top
  var draw = bids.slice().sort(function (a, b) { return (a.qualified - b.qualified) || (a.lev - b.lev); });
  var labels = el('g', { 'pointer-events': 'none' }, null);
  draw.forEach(function (b) {
    var x1 = X(b.asbid), x2 = X(b.lev), yy = Y(b.cov), g = el('g', { 'class': b.qualified ? '' : 'faded' }, svg);
    if (b.cov > 0.999) { // dodge inside the lane so equal-coverage bidders do not overprint
      var lo2 = Math.min(x1, x2) - 8, hi2 = Math.max(x1, x2) + 8, o = 0;
      for (var q = 0; q < OFF.length; q++) { o = OFF[q]; if (!placed.some(function (p) { return p.o === o && p.lo < hi2 && p.hi > lo2; })) break; }
      placed.push({ o: o, lo: lo2, hi: hi2 }); yy = laneY + o;
    }
    var isRec = M.rec && b.id === M.rec.id, isSel = b.id === state.sel;
    el('line', { x1: x1, x2: x2, y1: yy, y2: yy, stroke: b.plugs > 0 ? 'var(--plug-ink)' : 'var(--ink-2)', 'stroke-width': 2 }, g);
    el('line', { x1: x1, x2: x1, y1: yy - 5, y2: yy + 5, stroke: 'var(--ink-2)', 'stroke-width': 2, 'stroke-linecap': 'round' }, g);
    if (b.qualified) el('circle', { cx: x2, cy: yy, r: isRec ? 7.5 : 5.5, style: 'fill:var(--ink)', stroke: 'var(--surface)', 'stroke-width': 2 }, g);
    else el('circle', { cx: x2, cy: yy, r: 4, style: 'fill:var(--surface)', stroke: 'var(--ink-2)', 'stroke-width': 1.5 }, g);
    if (isSel) el('circle', { cx: x2, cy: yy, r: 10, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2 }, svg);
    var lab = null;
    if (isRec) lab = '★ ' + trunc(b.name, 24) + '  ' + short(b.lev);
    else if (isSel) lab = b.code + '  ' + trunc(b.name, 22);
    else if (b.qualified && nQ <= 16) lab = b.code;
    else if (b === lowAs && N > 3) lab = b.code + '  lowest as bid';
    else if (!b.qualified && N <= 8) lab = b.code;
    if (lab) { var rightSide = isRec ? x2 - left < 210 : x2 < left + plotW - 170; el('text', { x: x2 + (rightSide ? 12 : -12), y: yy + 4, 'text-anchor': rightSide ? 'start' : 'end', 'font-size': 11, 'font-weight': b.qualified ? 700 : 400, style: 'fill:var(--' + (b.qualified ? 'ink' : 'ink-2') + ');paint-order:stroke;stroke:var(--surface);stroke-width:3.5px' }, labels, lab); }
    pts.push({ b: b, x: x2, y: yy, x1: x1 });
  });
  svg.appendChild(labels);
  var hit = el('rect', { x: left, y: top, width: plotW, height: plotH, fill: 'transparent', style: 'cursor:pointer' }, svg);
  var ring = el('circle', { r: 10, fill: 'none', stroke: 'var(--ink)', 'stroke-width': 1.5, visibility: 'hidden', 'pointer-events': 'none' }, svg), lastId = null;
  function near(ev) { var bb = svg.getBoundingClientRect(), px = ev.clientX - bb.left, py = ev.clientY - bb.top, best = null, bd = 40 * 40; pts.forEach(function (p) { var d = Math.min(Math.pow(p.x - px, 2), Math.pow(p.x1 - px, 2)) + Math.pow(p.y - py, 2); if (d < bd) { bd = d; best = p; } }); return best; }
  function show(p) { if (!p) { ring.setAttribute('visibility', 'hidden'); return; } ring.setAttribute('cx', p.x); ring.setAttribute('cy', p.y); ring.setAttribute('visibility', 'visible'); }
  function tell(id) { if (id !== lastId) { lastId = id; if (opt.onHover) opt.onHover(id); } }
  hit.addEventListener('pointermove', function (ev) { var p = near(ev); show(p); if (!p) { app.hideTip(); tell(null); return; } app.bidderTip(ev, p.b.id); tell(p.b.id); });
  hit.addEventListener('pointerleave', function () { show(null); app.hideTip(); tell(null); });
  hit.addEventListener('click', function (ev) { var p = near(ev); if (p) app.onBidder(p.b.id); });
  return { highlight: function (id) { show(pts.filter(function (p) { return p.b.id === id; })[0] || null); } };
}


export { drawHeat, drawMap };
