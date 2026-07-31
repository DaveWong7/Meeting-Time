"""
When Can We Meet? — a tiny shared scheduler for a group call.

The poll covers one week, Monday through Sunday, in Mountain Time. Filling in
closes at 12:00 am Mountain on the Monday the week starts, after which the page
becomes read-only and just shows the result.

The drag-select calendar is embedded in this file, so app.py + storage.py +
requirements.txt is the whole app.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

import streamlit as st
import streamlit.components.v1 as components

import storage

# --------------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------------- #
MT = ZoneInfo("America/Denver")
SLOT_MINUTES = 30
DAYS_IN_POLL = 7

# Change this if you like. It can also be set as `admin_password` in secrets.
ORGANIZER_PASSWORD = "deleteeverything67"

PALETTE = [
    "#e4572e", "#2e86ab", "#8a4fff", "#3fa34d", "#d9a12b", "#c0399f", "#00897b",
    "#5a6acf", "#b5651d", "#0f9dd6", "#7cb518", "#d64550", "#6d4c9f", "#0b7a75",
]

VIEW_ME = "Fill in my times"
VIEW_GROUP = "See everyone"

COMMON_TZ = [
    "America/Denver", "America/Los_Angeles", "America/Phoenix", "America/Chicago",
    "America/New_York", "America/Anchorage", "Pacific/Honolulu", "America/Toronto",
    "America/Mexico_City", "America/Sao_Paulo", "Europe/London", "Europe/Dublin",
    "Europe/Lisbon", "Europe/Madrid", "Europe/Paris", "Europe/Berlin", "Europe/Rome",
    "Europe/Athens", "Europe/Warsaw", "Europe/Istanbul", "Europe/Moscow", "Asia/Jerusalem",
    "Asia/Dubai", "Asia/Karachi", "Asia/Kolkata", "Asia/Kathmandu", "Asia/Dhaka",
    "Asia/Bangkok", "Asia/Jakarta", "Asia/Singapore", "Asia/Hong_Kong", "Asia/Shanghai",
    "Asia/Taipei", "Asia/Seoul", "Asia/Tokyo", "Australia/Perth", "Australia/Brisbane",
    "Australia/Sydney", "Pacific/Auckland", "UTC",
]

st.set_page_config(page_title="When can we meet?", page_icon="🗓️", layout="wide")

# --------------------------------------------------------------------------- #
# the drag-select calendar, written out at startup so there is no second
# folder to upload and no "No such component directory" error
# --------------------------------------------------------------------------- #
GRID_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root {
    --bg: #ffffff;
    --panel: #f3f4f8;
    --text: #16181d;
    --muted: #6b7280;
    --line: #d9dce4;
    --line-strong: #b6bbc7;
    --on: #2f7d5d;
    --on-soft: #dff0e7;
    --erase: #c8553d;
    --star: #d99000;
    --radius: 3px;
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body {
    margin: 0; padding: 0; background: transparent; color: var(--text);
    font-family: var(--font, "Source Sans Pro", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
    font-size: 13px;
  }
  #root { padding: 2px 0 8px 0; }

  .toolbar {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    margin: 0 0 8px 0; color: var(--muted); font-size: 12px;
  }
  .hint { letter-spacing: .01em; }
  .modebtn {
    border: 1px solid var(--line-strong); background: var(--bg); color: var(--text);
    padding: 4px 10px; border-radius: 99px; font-size: 12px; cursor: pointer;
    font-family: inherit;
  }
  .modebtn[data-active="scroll"] { background: var(--panel); }

  .wrap { overflow-x: auto; overflow-y: hidden; padding-bottom: 4px; }
  .wrap.scrolling { touch-action: auto; }
  .wrap.painting { touch-action: none; }

  .grid {
    display: grid;
    min-width: max-content;
    user-select: none; -webkit-user-select: none;
  }

  .hcell {
    padding: 4px 2px 6px 2px; text-align: center; line-height: 1.15;
    border-bottom: 1px solid var(--line-strong);
    position: sticky; top: 0; background: var(--bg); z-index: 2;
  }
  .hcell .dow { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
  .hcell .day { font-size: 14px; font-weight: 600; }
  .hcell .tag { font-size: 10px; color: var(--on); letter-spacing: .04em; text-transform: uppercase; }
  .hcell.clickable { cursor: pointer; }
  .hcell.clickable:hover .day { text-decoration: underline; text-underline-offset: 3px; }
  .hcell.weekend .day { color: var(--muted); }

  .corner { position: sticky; left: 0; top: 0; background: var(--bg); z-index: 3; border-bottom: 1px solid var(--line-strong); }

  .tlabel {
    position: sticky; left: 0; background: var(--bg); z-index: 1;
    font-size: 11px; color: var(--muted); text-align: right;
    padding: 0 8px 0 2px; line-height: 1;
    display: flex; align-items: center; justify-content: flex-end;
    font-variant-numeric: tabular-nums;
  }
  .tlabel.clickable { cursor: pointer; }
  .tlabel.clickable:hover { color: var(--text); text-decoration: underline; }

  .cell {
    border-right: 1px solid var(--line);
    border-bottom: 1px dotted var(--line);
    background: var(--panel);
    position: relative;
  }
  .cell.hourline { border-bottom: 1px solid var(--line-strong); }
  .cell.daystart { border-left: 1px solid var(--line-strong); }
  .cell.lastcol { border-right: 1px solid var(--line-strong); }

  /* ---- edit mode ---- */
  .edit .cell { cursor: crosshair; }
  .edit .cell.on { background: var(--on); }
  .edit .cell.pv-add { background: var(--on-soft); box-shadow: inset 0 0 0 1px var(--on); }
  .edit .cell.pv-del { background: #f7e2dd; box-shadow: inset 0 0 0 1px var(--erase); }

  /* ---- view mode ---- */
  .view .cell { cursor: default; }
  .view .cell .n {
    position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 700; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,.45);
    font-variant-numeric: tabular-nums; pointer-events: none;
  }
  .view .cell.best { box-shadow: inset 0 0 0 2px var(--star); z-index: 1; }
  .view .cell.dim .n { color: var(--muted); text-shadow: none; }
  .view .cell.me { outline: 2px dashed #111; outline-offset: -2px; z-index: 2; }

  .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 10px; font-size: 12px; color: var(--muted); }
  .legend .item { display: flex; align-items: center; gap: 6px; }
  .swatch { width: 11px; height: 11px; border-radius: 2px; display: inline-block; }
  .empty { padding: 18px 4px; color: var(--muted); font-size: 13px; }
</style>
</head>
<body>
<div id="root"></div>
<script>
/* ------------------------------------------------------------------ */
/* Minimal Streamlit component protocol (no build step required)       */
/* ------------------------------------------------------------------ */
function _post(type, data) {
  window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: type }, data), "*");
}
const Streamlit = {
  ready: () => _post("streamlit:componentReady", { apiVersion: 1 }),
  height: (h) => _post("streamlit:setFrameHeight", { height: h }),
  value: (v) => _post("streamlit:setComponentValue", { value: v, dataType: "json" })
};

/* ------------------------------------------------------------------ */
/* State                                                               */
/* ------------------------------------------------------------------ */
const S = {
  args: null,
  sel: new Set(),
  epoch: null,
  structKey: null,
  cells: new Map(),      // key -> element
  dragging: false,
  dragMode: "add",
  anchor: null,          // {d, t}
  cursor: null,
  touchPaint: true
};

function keyOf(dateStr, timeStr) { return dateStr + " " + timeStr; }

function structSignature(a) {
  return JSON.stringify([a.mode, a.days, a.times, a.counts, a.names, a.best, a.colors, a.me]);
}

/* ------------------------------------------------------------------ */
/* Render entry                                                        */
/* ------------------------------------------------------------------ */
window.addEventListener("message", (e) => {
  if (!e.data || e.data.type !== "streamlit:render") return;
  applyTheme(e.data.theme);
  onRender(e.data.args || {});
});

function applyTheme(theme) {
  if (!theme) return;
  const r = document.documentElement.style;
  const dark = theme.base === "dark";
  r.setProperty("--bg", theme.backgroundColor || (dark ? "#0e1117" : "#ffffff"));
  r.setProperty("--panel", theme.secondaryBackgroundColor || (dark ? "#20242d" : "#f3f4f8"));
  r.setProperty("--text", theme.textColor || (dark ? "#e8eaf0" : "#16181d"));
  r.setProperty("--line", dark ? "#343a46" : "#d9dce4");
  r.setProperty("--line-strong", dark ? "#4a5162" : "#b6bbc7");
  r.setProperty("--muted", dark ? "#9aa2b1" : "#6b7280");
  if (theme.font) r.setProperty("--font", theme.font);
}

function onRender(args) {
  const sig = structSignature(args);
  const structChanged = sig !== S.structKey;
  const epochChanged = String(args.epoch) !== String(S.epoch);

  S.args = args;
  if (epochChanged) {
    S.sel = new Set(args.selected || []);
    S.epoch = args.epoch;
  }
  if (structChanged) {
    S.structKey = sig;
    build();
  }
  paint();
  resize();
}

function resize() {
  Streamlit.height(document.documentElement.scrollHeight + 4);
}
window.addEventListener("resize", resize);

/* ------------------------------------------------------------------ */
/* Build DOM                                                           */
/* ------------------------------------------------------------------ */
function build() {
  const a = S.args;
  const root = document.getElementById("root");
  root.innerHTML = "";
  S.cells = new Map();

  const days = a.days || [];
  const times = a.times || [];
  const edit = a.mode === "edit";

  if (!days.length || !times.length) {
    root.innerHTML = '<div class="empty">No dates to show. Adjust the date range in the sidebar.</div>';
    return;
  }
  if (!edit && (!a.people || !a.people.length)) {
    root.innerHTML = '<div class="empty">Nobody has submitted yet. Be the first — fill in your times on the “My availability” tab.</div>';
    return;
  }

  /* toolbar */
  const bar = document.createElement("div");
  bar.className = "toolbar";
  if (edit) {
    const hint = document.createElement("span");
    hint.className = "hint";
    hint.textContent = "Click and drag to paint the times you’re free. Drag over filled cells to erase. Click a date or a time label to fill a whole column or row.";
    bar.appendChild(hint);

    const btn = document.createElement("button");
    btn.className = "modebtn";
    btn.type = "button";
    const setLabel = () => {
      btn.textContent = S.touchPaint ? "Touch: painting" : "Touch: scrolling";
      btn.dataset.active = S.touchPaint ? "paint" : "scroll";
      wrap.className = "wrap " + (S.touchPaint ? "painting" : "scrolling");
    };
    btn.addEventListener("click", () => { S.touchPaint = !S.touchPaint; setLabel(); });
    bar.appendChild(btn);
    var _setLabel = setLabel;
  } else {
    const hint = document.createElement("span");
    hint.className = "hint";
    hint.textContent = "Darker cell = more people free. Gold outline = best slot(s) for the meeting length you picked. Hover a cell to see who’s free.";
    bar.appendChild(hint);
  }
  root.appendChild(bar);

  /* grid */
  const wrap = document.createElement("div");
  wrap.className = "wrap " + (edit ? "painting" : "scrolling");

  const grid = document.createElement("div");
  grid.className = "grid " + (edit ? "edit" : "view");
  const colW = days.length > 10 ? 62 : 78;
  grid.style.gridTemplateColumns = `56px repeat(${days.length}, minmax(${colW}px, 1fr))`;
  grid.style.gridAutoRows = "22px";

  /* header row */
  const corner = document.createElement("div");
  corner.className = "corner hcell";
  corner.innerHTML = '<div class="dow">MT</div>';
  corner.title = "All times are Mountain Time (America/Denver)";
  grid.appendChild(corner);

  days.forEach((d, di) => {
    const h = document.createElement("div");
    h.className = "hcell" + (d.weekend ? " weekend" : "") + (edit ? " clickable" : "");
    h.innerHTML =
      `<div class="dow">${d.dow}</div><div class="day">${d.label}</div>` +
      (d.tag ? `<div class="tag">${d.tag}</div>` : "");
    if (edit) {
      h.title = "Click to select / clear this whole day";
      h.addEventListener("click", () => toggleBlock(di, di, 0, times.length - 1));
    }
    grid.appendChild(h);
  });

  /* body rows */
  times.forEach((t, ti) => {
    const lab = document.createElement("div");
    lab.className = "tlabel" + (edit ? " clickable" : "");
    lab.textContent = t.major ? t.label : "";
    if (edit) {
      lab.title = "Click to select / clear this time across every day";
      lab.addEventListener("click", () => toggleBlock(0, days.length - 1, ti, ti));
    }
    grid.appendChild(lab);

    days.forEach((d, di) => {
      const c = document.createElement("div");
      const k = keyOf(d.date, t.value);
      c.className = "cell" +
        (times[ti + 1] && times[ti + 1].major ? " hourline" : "") +
        (ti === times.length - 1 ? " hourline" : "") +
        (di === days.length - 1 ? " lastcol" : "");
      c.dataset.d = di; c.dataset.t = ti; c.dataset.k = k;
      if (!edit) {
        const n = document.createElement("span");
        n.className = "n";
        c.appendChild(n);
      }
      grid.appendChild(c);
      S.cells.set(k, c);
    });
  });

  wrap.appendChild(grid);
  root.appendChild(wrap);
  if (edit && typeof _setLabel === "function") _setLabel();

  if (!edit && S.args.people && S.args.people.length) {
    const leg = document.createElement("div");
    leg.className = "legend";
    S.args.people.forEach((p) => {
      const it = document.createElement("div");
      it.className = "item";
      it.innerHTML = `<span class="swatch" style="background:${(S.args.colors || {})[p] || "#888"}"></span>${escapeHtml(p)}`;
      leg.appendChild(it);
    });
    root.appendChild(leg);
  }

  if (edit) attachDrag(grid);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ------------------------------------------------------------------ */
/* Painting classes / colors                                           */
/* ------------------------------------------------------------------ */
function paint() {
  const a = S.args;
  if (!a) return;
  const edit = a.mode === "edit";

  if (edit) {
    const pv = previewSet();
    S.cells.forEach((c, k) => {
      c.classList.toggle("on", S.sel.has(k));
      c.classList.toggle("pv-add", pv.add.has(k));
      c.classList.toggle("pv-del", pv.del.has(k));
    });
    return;
  }

  const counts = a.counts || {};
  const names = a.names || {};
  const colors = a.colors || {};
  const best = new Set(a.best || []);
  const total = Math.max(1, (a.people || []).length);
  const mine = new Set(a.me_slots || []);

  S.cells.forEach((c, k) => {
    const who = names[k] || [];
    const n = counts[k] || 0;
    const label = c.querySelector(".n");
    if (who.length) {
      const stops = [];
      const step = 100 / who.length;
      who.forEach((p, i) => {
        const col = colors[p] || "#7a8699";
        stops.push(`${col} ${i * step}%`, `${col} ${(i + 1) * step}%`);
      });
      c.style.background = `linear-gradient(180deg, ${stops.join(",")})`;
      c.style.opacity = String(0.42 + 0.58 * (n / total));
      if (label) label.textContent = n > 1 ? n : "";
      c.classList.remove("dim");
      c.title = `${k} MT — ${n}/${total} free\n${who.join(", ")}`;
    } else {
      c.style.background = "";
      c.style.opacity = "";
      if (label) label.textContent = "";
      c.classList.add("dim");
      c.title = `${k} MT — nobody free`;
    }
    c.classList.toggle("best", best.has(k));
    c.classList.toggle("me", mine.has(k));
  });
}

function previewSet() {
  const add = new Set(), del = new Set();
  if (!S.dragging || !S.anchor || !S.cursor) return { add, del };
  const days = S.args.days, times = S.args.times;
  const d0 = Math.min(S.anchor.d, S.cursor.d), d1 = Math.max(S.anchor.d, S.cursor.d);
  const t0 = Math.min(S.anchor.t, S.cursor.t), t1 = Math.max(S.anchor.t, S.cursor.t);
  for (let d = d0; d <= d1; d++) {
    for (let t = t0; t <= t1; t++) {
      const k = keyOf(days[d].date, times[t].value);
      (S.dragMode === "add" ? add : del).add(k);
    }
  }
  return { add, del };
}

/* ------------------------------------------------------------------ */
/* Drag interaction                                                    */
/* ------------------------------------------------------------------ */
function cellFromEvent(e) {
  let el = e.target;
  if (e.touches && e.touches.length) {
    const t = e.touches[0];
    el = document.elementFromPoint(t.clientX, t.clientY);
  }
  if (!el || !el.classList || !el.classList.contains("cell")) return null;
  return { d: +el.dataset.d, t: +el.dataset.t, k: el.dataset.k };
}

function attachDrag(grid) {
  const start = (e) => {
    if (e.type === "touchstart" && !S.touchPaint) return;
    const c = cellFromEvent(e);
    if (!c) return;
    if (e.cancelable) e.preventDefault();
    S.dragging = true;
    S.dragMode = S.sel.has(c.k) ? "del" : "add";
    S.anchor = c; S.cursor = c;
    paint();
  };
  const move = (e) => {
    if (!S.dragging) return;
    const c = cellFromEvent(e);
    if (!c) return;
    if (e.cancelable) e.preventDefault();
    if (S.cursor && c.d === S.cursor.d && c.t === S.cursor.t) return;
    S.cursor = c;
    paint();
  };
  const end = () => {
    if (!S.dragging) return;
    const pv = previewSet();
    pv.add.forEach((k) => S.sel.add(k));
    pv.del.forEach((k) => S.sel.delete(k));
    S.dragging = false; S.anchor = null; S.cursor = null;
    paint();
    commit();
  };

  grid.addEventListener("mousedown", start);
  grid.addEventListener("mouseover", move);
  window.addEventListener("mouseup", end);
  grid.addEventListener("touchstart", start, { passive: false });
  grid.addEventListener("touchmove", move, { passive: false });
  window.addEventListener("touchend", end);
  window.addEventListener("touchcancel", end);
}

function toggleBlock(d0, d1, t0, t1) {
  const days = S.args.days, times = S.args.times;
  const keys = [];
  for (let d = d0; d <= d1; d++) for (let t = t0; t <= t1; t++) keys.push(keyOf(days[d].date, times[t].value));
  const allOn = keys.every((k) => S.sel.has(k));
  keys.forEach((k) => (allOn ? S.sel.delete(k) : S.sel.add(k)));
  paint();
  commit();
}

function commit() {
  Streamlit.value({ slots: Array.from(S.sel).sort(), epoch: S.args.epoch });
}

Streamlit.ready();
Streamlit.height(320);
</script>
</body>
</html>
"""


def _component_dir() -> Path:
    folder = Path(tempfile.gettempdir()) / "availability_grid_frontend"
    folder.mkdir(parents=True, exist_ok=True)
    index = folder / "index.html"
    if not index.exists() or index.read_text("utf-8") != GRID_HTML:
        index.write_text(GRID_HTML, "utf-8")
    return folder


_grid = components.declare_component("availability_grid", path=str(_component_dir()))


def availability_grid(*, days, times, mode, epoch, key, selected=None, counts=None,
                      names=None, colors=None, best=None, people=None, me_slots=None):
    return _grid(
        days=days, times=times, mode=mode, epoch=epoch,
        selected=selected or [], counts=counts or {}, names=names or {},
        colors=colors or {}, best=best or [], people=people or [], me_slots=me_slots or [],
        key=key, default=None,
    )


# --------------------------------------------------------------------------- #
# time helpers
# --------------------------------------------------------------------------- #
def now_mt() -> datetime:
    return datetime.now(MT)


def today_mt() -> date:
    return now_mt().date()


def next_monday(after: date | None = None) -> date:
    """The Monday of next week — always a future Monday, never today."""
    day = after or today_mt()
    return day + timedelta(days=(7 - day.weekday()) or 7)


def upcoming_mondays(count: int = 5) -> list[date]:
    first = next_monday()
    return [first + timedelta(weeks=i) for i in range(count)]


def build_days(week_start: date) -> list[dict]:
    t = today_mt()
    out = []
    for i in range(DAYS_IN_POLL):
        d = week_start + timedelta(days=i)
        tag = "Today" if d == t else ("Tomorrow" if d == t + timedelta(days=1) else "")
        out.append({
            "date": d.isoformat(),
            "dow": d.strftime("%a"),
            "label": d.strftime("%b ") + str(d.day),
            "weekend": d.weekday() >= 5,
            "tag": tag,
        })
    return out


def build_times(start_hour: int, end_hour: int) -> list[dict]:
    out = []
    minute = start_hour * 60
    while minute < end_hour * 60:
        h, m = divmod(minute, 60)
        out.append({"value": f"{h:02d}:{m:02d}", "label": pretty_time(h, m), "major": m == 0})
        minute += SLOT_MINUTES
    return out


def pretty_time(h: int, m: int) -> str:
    suffix = "am" if h < 12 else "pm"
    hour12 = h % 12 or 12
    return f"{hour12}:{m:02d} {suffix}" if m else f"{hour12} {suffix}"


def pretty_date(d: date) -> str:
    return d.strftime("%a %b ") + str(d.day)


def countdown(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days} day{'s' if days != 1 else ''}, {hours} hr{'s' if hours != 1 else ''}"
    if hours:
        return f"{hours} hr{'s' if hours != 1 else ''}, {minutes} min"
    return f"{minutes} min"


def slot_key(day: str, tvalue: str) -> str:
    return f"{day} {tvalue}"


def slot_dt(key: str) -> datetime:
    return datetime.strptime(key, "%Y-%m-%d %H:%M").replace(tzinfo=MT)


def fmt_span(day: str, start_value: str, minutes: int, tz: ZoneInfo | None = None) -> str:
    begin = slot_dt(slot_key(day, start_value))
    finish = begin + timedelta(minutes=minutes)
    if tz:
        begin, finish = begin.astimezone(tz), finish.astimezone(tz)
    a = pretty_time(begin.hour, begin.minute)
    b = pretty_time(finish.hour, finish.minute)
    tail = "" if begin.date() == finish.date() else " (+1 day)"
    return f"{pretty_date(begin.date())}, {a} – {b}{tail}"


# --------------------------------------------------------------------------- #
# data helpers
# --------------------------------------------------------------------------- #
def organizer_password() -> str:
    try:
        return str(st.secrets.get("admin_password") or ORGANIZER_PASSWORD)
    except Exception:
        return ORGANIZER_PASSWORD


def get_settings(data: dict) -> dict:
    s = dict(data.get("settings") or {})
    s.setdefault("title", "Group call")
    s.setdefault("start_hour", 8)
    s.setdefault("end_hour", 22)
    s.setdefault("week_start", next_monday().isoformat())
    s.setdefault("force_open", False)
    return s


def person_colors(people: list[str]) -> dict[str, str]:
    return {p: PALETTE[i % len(PALETTE)] for i, p in enumerate(people)}


def find_person(data: dict, name: str) -> str | None:
    target = name.strip().casefold()
    for existing in data["people"]:
        if existing.casefold() == target:
            return existing
    return None


# --------------------------------------------------------------------------- #
# overlap maths
# --------------------------------------------------------------------------- #
def merged_windows(days, times, slots_by_person, participants, slots_needed):
    """Every place a meeting of the requested length fits, best-attended first."""
    raw = []
    for day in days:
        for i in range(len(times) - slots_needed + 1):
            keys = [slot_key(day["date"], times[j]["value"]) for j in range(i, i + slots_needed)]
            free = [p for p in participants if all(k in slots_by_person[p] for k in keys)]
            if not free:
                continue
            raw.append({"date": day["date"], "start_idx": i, "end_idx": i + slots_needed - 1,
                        "free": frozenset(free), "keys": keys})

    merged: list[dict] = []
    for w in sorted(raw, key=lambda w: (w["date"], w["start_idx"])):
        last = merged[-1] if merged else None
        if (last and last["date"] == w["date"] and last["free"] == w["free"]
                and w["start_idx"] <= last["end_idx"] + 1):
            last["end_idx"] = max(last["end_idx"], w["end_idx"])
            last["keys"] = sorted(set(last["keys"]) | set(w["keys"]))
        else:
            merged.append(dict(w))

    for w in merged:
        w["score"] = len(w["free"])
        w["start_value"] = times[w["start_idx"]]["value"]
        w["span_minutes"] = (w["end_idx"] - w["start_idx"] + 1) * SLOT_MINUTES
    merged.sort(key=lambda w: (-w["score"], w["date"], w["start_idx"]))
    return merged


def make_ics(title: str, day: str, start_value: str, minutes: int, attendees: list[str]) -> str:
    begin = slot_dt(slot_key(day, start_value)).astimezone(ZoneInfo("UTC"))
    finish = begin + timedelta(minutes=minutes)
    stamp = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//when-can-we-meet//EN",
        "CALSCALE:GREGORIAN", "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@when-can-we-meet",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{begin.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{finish.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:Everyone free: {', '.join(attendees)}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


# --------------------------------------------------------------------------- #
# load state
# --------------------------------------------------------------------------- #
data = storage.load_data()
settings = get_settings(data)

# Pin the week the first time anyone opens the app, so it can't quietly roll
# forward to a different week the moment the deadline passes.
if not (data.get("settings") or {}).get("week_start"):
    data["settings"] = settings
    storage.save_data(data)

week_start = date.fromisoformat(settings["week_start"])
week_end = week_start + timedelta(days=DAYS_IN_POLL - 1)
deadline = datetime.combine(week_start, datetime.min.time(), tzinfo=MT)  # Monday 12:00 am MT
time_left = deadline - now_mt()
past_deadline = time_left.total_seconds() <= 0
is_open = (not past_deadline) or bool(settings.get("force_open"))

st.session_state.setdefault("draft", [])
st.session_state.setdefault("epoch", 0)
st.session_state.setdefault("view", VIEW_ME)
st.session_state.setdefault("name_input", "")
st.session_state.setdefault("pending_delete", None)
st.session_state.setdefault("just_saved", None)
st.session_state.setdefault("goto", None)
st.session_state.setdefault("pending_name", None)

# Widget keys can only be written before their widget is built, so anything that
# wants to move the user somewhere sets a flag and it lands here on the next run.
if st.session_state.goto:
    st.session_state.view = st.session_state.goto
    st.session_state.goto = None
if st.session_state.pending_name is not None:
    st.session_state.name_input = st.session_state.pending_name
    st.session_state.pending_name = None

days = build_days(week_start)
times = build_times(int(settings["start_hour"]), int(settings["end_hour"]))
visible_keys = {slot_key(d["date"], t["value"]) for d in days for t in times}

people = list(data["people"].keys())
colors = person_colors(people)
slots_by_person = {p: set(data["people"][p].get("slots", [])) & visible_keys for p in people}


def start_editing(person: str) -> None:
    st.session_state.pending_name = person
    st.session_state.draft = sorted(slots_by_person.get(person, set()))
    st.session_state.epoch += 1
    st.session_state.goto = VIEW_ME
    st.session_state.pending_delete = None


# --------------------------------------------------------------------------- #
# sidebar — status for everyone, tools behind the password
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.subheader("The week being planned")
    st.write(f"**{pretty_date(week_start)} – {pretty_date(week_end)}**")
    if is_open and not past_deadline:
        st.success(f"Open for another **{countdown(time_left)}**")
        st.caption(f"Closes {pretty_date(week_start)} at 12:00 am Mountain.")
    elif is_open:
        st.warning("Past the deadline, reopened by the organizer.")
    else:
        st.error("Closed. The times below are final.")
    st.caption(f"{len(people)} {'answer' if len(people) == 1 else 'answers'} so far.")

    st.divider()
    with st.expander("Organizer tools"):
        entered = st.text_input("Organizer password", type="password", key="admin_pw")
        if entered and entered != organizer_password():
            st.error("Wrong password.")
        elif entered == organizer_password():
            st.caption(f"Saving to: {storage.backend_name()}")

            with st.form("settings_form"):
                title = st.text_input("Meeting name", value=settings["title"])
                hour_range = st.slider("Hours shown each day (MT)", 0, 24,
                                       (int(settings["start_hour"]), int(settings["end_hour"])))
                options = sorted(set(upcoming_mondays()) | {week_start})
                labels = [f"{pretty_date(m)} – {pretty_date(m + timedelta(days=6))}" for m in options]
                picked_week = st.selectbox("Week to plan", labels, index=options.index(week_start))
                keep_open = st.checkbox(
                    "Keep filling in open past the deadline", value=bool(settings.get("force_open"))
                )
                if st.form_submit_button("Save settings", use_container_width=True):
                    if hour_range[0] >= hour_range[1]:
                        st.error("The end hour has to be after the start hour.")
                    else:
                        fresh = storage.load_data()
                        fresh["settings"] = {
                            "title": title.strip() or "Group call",
                            "start_hour": int(hour_range[0]),
                            "end_hour": int(hour_range[1]),
                            "week_start": options[labels.index(picked_week)].isoformat(),
                            "force_open": bool(keep_open),
                        }
                        storage.save_data(fresh)
                        st.rerun()

            st.download_button(
                "Download a backup",
                data=json.dumps(data, indent=2),
                file_name="availability-backup.json",
                mime="application/json",
                use_container_width=True,
            )
            restore = st.file_uploader("Restore a backup", type="json")
            if restore is not None and st.button("Restore this file", use_container_width=True):
                try:
                    storage.save_data(json.loads(restore.read().decode("utf-8")))
                    st.success("Restored.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"That file didn't load: {exc}")

            st.divider()
            st.caption("Start clean — use this once you're done testing.")
            if st.button("Delete every answer", use_container_width=True):
                st.session_state.pending_delete = "__all__"
            if st.session_state.pending_delete == "__all__":
                st.warning(f"This deletes all {len(people)} answers. There's no undo.")
                c1, c2 = st.columns(2)
                if c1.button("Delete them", use_container_width=True):
                    fresh = storage.load_data()
                    fresh["people"] = {}
                    storage.save_data(fresh)
                    st.session_state.pending_delete = None
                    st.session_state.draft = []
                    st.session_state.epoch += 1
                    st.rerun()
                if c2.button("Cancel", use_container_width=True):
                    st.session_state.pending_delete = None
                    st.rerun()
        else:
            st.caption("Settings, backups and resetting live here.")

# --------------------------------------------------------------------------- #
# header
# --------------------------------------------------------------------------- #
st.title(settings["title"])
st.caption(
    f"**{pretty_date(week_start)} – {pretty_date(week_end)}**, all in **Mountain Time** "
    f"({now_mt():%b %d, %I:%M %p} MT right now). "
    + (f"Filling in closes {pretty_date(week_start)} at 12:00 am MT — {countdown(time_left)} left."
       if is_open and not past_deadline
       else ("Filling in is reopened past its deadline." if is_open
             else f"Filling in closed {pretty_date(week_start)} at 12:00 am MT."))
)

st.radio("Section", [VIEW_ME, VIEW_GROUP], key="view", horizontal=True, label_visibility="collapsed")

# --------------------------------------------------------------------------- #
# view: fill in my times
# --------------------------------------------------------------------------- #
if st.session_state.view == VIEW_ME:
    if st.session_state.just_saved:
        st.success(f"Saved {st.session_state.just_saved}. Switch to “See everyone” to compare.")
        st.session_state.just_saved = None

    if not is_open:
        st.info(
            f"Filling in closed at 12:00 am Mountain on {pretty_date(week_start)}. "
            "Head to “See everyone” for the result."
        )
        st.stop()

    left, right = st.columns([2, 3])
    with left:
        name = st.text_input("Your name", key="name_input", placeholder="e.g. Sam")
    match = find_person(data, name) if name.strip() else None
    with right:
        st.write("")
        if match:
            st.info(f"**{match}** already answered. Saving will replace their times.")
            if st.button(f"Load {match}'s saved times"):
                start_editing(match)
                st.rerun()

    b1, b2, b3, _ = st.columns([1, 1, 1, 3])
    if b1.button("Clear all", use_container_width=True):
        st.session_state.draft = []
        st.session_state.epoch += 1
        st.rerun()
    if b2.button("Select all", use_container_width=True):
        st.session_state.draft = sorted(visible_keys)
        st.session_state.epoch += 1
        st.rerun()
    if b3.button("Evenings only", use_container_width=True,
                 help="Weekdays 5pm–10pm plus all weekend, as a starting point"):
        picked = set()
        for d in days:
            for t in times:
                hour = int(t["value"][:2])
                if d["weekend"] or 17 <= hour < 22:
                    picked.add(slot_key(d["date"], t["value"]))
        st.session_state.draft = sorted(picked)
        st.session_state.epoch += 1
        st.rerun()

    result = availability_grid(
        days=days, times=times, mode="edit",
        selected=st.session_state.draft, epoch=st.session_state.epoch, key="grid_edit",
    )
    if isinstance(result, dict) and str(result.get("epoch")) == str(st.session_state.epoch):
        st.session_state.draft = result.get("slots", [])

    chosen = len(st.session_state.draft)
    st.caption(f"{chosen} slots selected — {chosen * SLOT_MINUTES / 60:g} hours.")

    save_col, _ = st.columns([1, 3])
    if save_col.button("Save my availability", type="primary", use_container_width=True,
                       disabled=not name.strip()):
        if not st.session_state.draft:
            st.error("Pick at least one time before saving.")
        else:
            fresh = storage.load_data()
            label = match or name.strip()
            keep = set(fresh["people"].get(label, {}).get("slots", [])) - visible_keys
            fresh["people"][label] = {
                "slots": sorted(set(st.session_state.draft) | keep),
                "updated": now_mt().isoformat(timespec="seconds"),
            }
            storage.save_data(fresh)
            st.session_state.just_saved = label
            st.session_state.goto = VIEW_GROUP
            st.rerun()
    if not name.strip():
        st.caption("Add your name to turn on saving.")

# --------------------------------------------------------------------------- #
# view: see everyone
# --------------------------------------------------------------------------- #
else:
    if st.session_state.just_saved:
        st.success(f"Saved {st.session_state.just_saved}'s times.")
        st.session_state.just_saved = None

    if not people:
        st.info(
            "No answers yet. Head to “Fill in my times” and go first."
            if is_open else "Nobody answered before the deadline."
        )
        st.stop()

    c1, c2, c3 = st.columns([3, 1.4, 1])
    with c1:
        participants = st.multiselect(
            "Who has to be there?", people, default=people,
            help="Untick anyone optional to see how the picture changes.",
        )
    with c2:
        length_label = st.selectbox("Meeting length", ["30 min", "1 hour", "1½ hours", "2 hours"], index=1)
    with c3:
        st.write("")
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    slots_needed = {"30 min": 1, "1 hour": 2, "1½ hours": 3, "2 hours": 4}[length_label]
    minutes_needed = slots_needed * SLOT_MINUTES

    if not participants:
        st.warning("Tick at least one person.")
        st.stop()

    counts, names_at = {}, {}
    for key in visible_keys:
        free = [p for p in participants if key in slots_by_person[p]]
        if free:
            counts[key] = len(free)
            names_at[key] = free

    windows = merged_windows(days, times, slots_by_person, participants, slots_needed)
    best_keys: list[str] = []
    top_score = windows[0]["score"] if windows else 0
    if windows:
        best_keys = sorted({k for w in windows if w["score"] == top_score for k in w["keys"]})

    if not windows:
        st.error(
            f"There is no {length_label} block where even one of these people is free. "
            "Try a shorter meeting, or a wider hour range."
        )
    else:
        winners = [w for w in windows if w["score"] == top_score]
        headline = ("Everyone can make it" if top_score == len(participants)
                    else f"Best so far: {top_score} of {len(participants)}")
        st.subheader(headline + ("" if len(winners) == 1 else f" — {len(winners)} equally good options"))

        for w in winners[:6]:
            gap = sorted(set(participants) - set(w["free"]))
            note = "everyone free" if not gap else "missing " + ", ".join(gap)
            span = ("" if w["span_minutes"] <= minutes_needed
                    else f"  ·  window open {w['span_minutes'] // 60}h{w['span_minutes'] % 60 or ''}")
            st.markdown(f"**{fmt_span(w['date'], w['start_value'], minutes_needed)}** — {note}{span}")
        if len(winners) > 6:
            st.caption(f"…and {len(winners) - 6} more just as good.")

        with st.expander("Next best options"):
            runners = [w for w in windows if w["score"] < top_score][:10]
            if not runners:
                st.caption("Nothing else comes close.")
            for w in runners:
                gap = sorted(set(participants) - set(w["free"]))
                st.markdown(
                    f"**{fmt_span(w['date'], w['start_value'], minutes_needed)}** — "
                    f"{w['score']} of {len(participants)}, missing {', '.join(gap)}"
                )

        st.write("")
        choices = winners[:10] + [w for w in windows if w["score"] < top_score][:10]
        labels = [f"{fmt_span(w['date'], w['start_value'], minutes_needed)}  ({w['score']}/{len(participants)})"
                  for w in choices]
        pick_col, tz_col = st.columns([2, 2])
        with pick_col:
            picked_label = st.selectbox("Lock one in", labels)
        picked = choices[labels.index(picked_label)]
        with tz_col:
            tz_options = COMMON_TZ + sorted(set(available_timezones()) - set(COMMON_TZ))
            tz_name = st.selectbox("Show that time in", tz_options, index=0)
        tz = ZoneInfo(tz_name)
        st.caption(
            f"{fmt_span(picked['date'], picked['start_value'], minutes_needed)} Mountain  →  "
            f"**{fmt_span(picked['date'], picked['start_value'], minutes_needed, tz)}** in {tz_name}"
        )

        summary = (
            f"{settings['title']}\n"
            f"{fmt_span(picked['date'], picked['start_value'], minutes_needed)} Mountain Time\n"
            f"Free: {', '.join(sorted(picked['free']))}\n"
            + (f"Can't make it: {', '.join(sorted(set(participants) - set(picked['free'])))}\n"
               if set(participants) - set(picked["free"]) else "")
        )
        d1, d2 = st.columns([1, 1])
        d1.download_button(
            "Download calendar invite (.ics)",
            data=make_ics(settings["title"], picked["date"], picked["start_value"],
                          minutes_needed, sorted(picked["free"])),
            file_name="meeting.ics", mime="text/calendar", use_container_width=True,
        )
        with d2.popover("Copy a summary", use_container_width=True):
            st.code(summary, language=None)

    st.write("")
    st.markdown("#### Everyone's times together")
    availability_grid(
        days=days, times=times, mode="view", epoch=st.session_state.epoch, key="grid_view",
        counts=counts, names=names_at, colors=colors, best=best_keys, people=participants,
    )

    st.write("")
    st.markdown("#### Who's answered")
    st.caption("Click Edit on your own row to change your times." if is_open
               else "Filling in is closed, so these can't be changed.")
    for person in people:
        row = st.columns([0.4, 3, 2, 1, 1])
        row[0].markdown(
            f"<div style='width:14px;height:14px;border-radius:3px;margin-top:8px;"
            f"background:{colors[person]}'></div>",
            unsafe_allow_html=True,
        )
        free_hours = len(slots_by_person[person]) * SLOT_MINUTES / 60
        row[1].markdown(f"**{person}**" + ("" if person in participants else "  ·  _not counted_"))
        updated = data["people"][person].get("updated", "")
        stamp = updated[:16].replace("T", " ") if updated else "—"
        row[2].caption(f"{free_hours:g} hours free · updated {stamp}")
        if row[3].button("Edit", key=f"edit_{person}", use_container_width=True, disabled=not is_open):
            start_editing(person)
            st.rerun()
        if row[4].button("Remove", key=f"del_{person}", use_container_width=True, disabled=not is_open):
            st.session_state.pending_delete = person
            st.rerun()

        if st.session_state.pending_delete == person:
            warn = st.columns([0.4, 3, 2])
            warn[1].warning(f"Remove {person}'s answer?")
            b = warn[2].columns(2)
            if b[0].button("Remove", key=f"yes_{person}", use_container_width=True):
                fresh = storage.load_data()
                fresh["people"].pop(person, None)
                storage.save_data(fresh)
                st.session_state.pending_delete = None
                st.rerun()
            if b[1].button("Cancel", key=f"no_{person}", use_container_width=True):
                st.session_state.pending_delete = None
                st.rerun()
