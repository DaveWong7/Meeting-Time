const fs = require("fs");
const { JSDOM } = require("jsdom");

const html = fs.readFileSync("/home/claude/meetup-picker/frontend/index.html", "utf8");

const days = [
  { date: "2026-08-01", dow: "Sat", label: "Aug 1", weekend: true, tag: "Today" },
  { date: "2026-08-02", dow: "Sun", label: "Aug 2", weekend: true, tag: "Tomorrow" },
  { date: "2026-08-03", dow: "Mon", label: "Aug 3", weekend: false, tag: "" },
];
const times = [
  { value: "18:00", label: "6 pm", major: true },
  { value: "18:30", label: "6:30 pm", major: false },
  { value: "19:00", label: "7 pm", major: true },
  { value: "19:30", label: "7:30 pm", major: false },
];

function boot() {
  const sent = [];
  const dom = new JSDOM(html, {
    runScripts: "dangerously",
    pretendToBeVisual: true,
    // hook in before the page script runs so the initial ready message is captured
    beforeParse(window) { window.postMessage = (msg) => sent.push(msg); },
  });
  return { dom, sent, w: dom.window };
}

function render(w, args, theme) {
  w.dispatchEvent(new w.MessageEvent("message", {
    data: { type: "streamlit:render", args, theme: theme || { base: "light" } },
  }));
}

function cell(w, d, t) {
  return w.document.querySelector(`.cell[data-d="${d}"][data-t="${t}"]`);
}

function drag(w, from, to) {
  const a = cell(w, from[0], from[1]);
  const b = cell(w, to[0], to[1]);
  a.dispatchEvent(new w.MouseEvent("mousedown", { bubbles: true }));
  b.dispatchEvent(new w.MouseEvent("mouseover", { bubbles: true }));
  w.dispatchEvent(new w.MouseEvent("mouseup", { bubbles: true }));
}

function lastValue(sent) {
  const vals = sent.filter((m) => m.type === "streamlit:setComponentValue");
  return vals.length ? vals[vals.length - 1].value : null;
}

let failures = 0;
function check(label, cond, extra) {
  if (cond) console.log("  ok   " + label);
  else { failures++; console.log("  FAIL " + label + (extra ? "  -> " + JSON.stringify(extra) : "")); }
}

/* ---------------- edit mode ---------------- */
console.log("edit mode");
{
  const { sent, w } = boot();
  render(w, { days, times, mode: "edit", epoch: 0, selected: [], counts: {}, names: {}, colors: {}, best: [], people: [], me_slots: [] });

  check("ready message sent", sent.some((m) => m.type === "streamlit:componentReady"));
  check("frame height sent", sent.some((m) => m.type === "streamlit:setFrameHeight"));
  check("cell count = days*times", w.document.querySelectorAll(".cell").length === 12,
        w.document.querySelectorAll(".cell").length);
  check("grid is in edit mode", !!w.document.querySelector(".grid.edit"));
  check("time labels only on the hour",
        w.document.querySelectorAll(".tlabel")[0].textContent === "6 pm" &&
        w.document.querySelectorAll(".tlabel")[1].textContent === "");

  // paint a 2x2 rectangle from (day1,slot1) to (day2,slot2)
  drag(w, [1, 1], [2, 2]);
  let v = lastValue(sent);
  check("drag paints a rectangle", JSON.stringify(v.slots) === JSON.stringify([
    "2026-08-02 18:30", "2026-08-02 19:00", "2026-08-03 18:30", "2026-08-03 19:00",
  ]), v.slots);
  check("value echoes epoch", v.epoch === 0);
  check("painted cells marked on", cell(w, 1, 1).classList.contains("on") && cell(w, 2, 2).classList.contains("on"));
  check("untouched cell stays off", !cell(w, 0, 0).classList.contains("on"));

  // dragging backwards over filled cells erases
  drag(w, [2, 2], [1, 2]);
  v = lastValue(sent);
  check("drag over filled cells erases", JSON.stringify(v.slots) === JSON.stringify([
    "2026-08-02 18:30", "2026-08-03 18:30",
  ]), v.slots);

  // clicking a day header toggles the whole column
  w.document.querySelectorAll(".hcell.clickable")[0].dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  v = lastValue(sent);
  check("day header fills the column", v.slots.filter((s) => s.startsWith("2026-08-01")).length === 4, v.slots);
  w.document.querySelectorAll(".hcell.clickable")[0].dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  v = lastValue(sent);
  check("day header clears it again", v.slots.filter((s) => s.startsWith("2026-08-01")).length === 0, v.slots);

  // clicking a time label toggles the row
  w.document.querySelectorAll(".tlabel.clickable")[2].dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  v = lastValue(sent);
  check("time label fills the row", v.slots.filter((s) => s.endsWith("19:00")).length === 3, v.slots);

  // a re-render with the same epoch must not wipe local selection
  const before = lastValue(sent).slots;
  render(w, { days, times, mode: "edit", epoch: 0, selected: [], counts: {}, names: {}, colors: {}, best: [], people: [], me_slots: [] });
  drag(w, [0, 0], [0, 0]);
  check("same epoch keeps what the user painted", lastValue(sent).slots.length === before.length + 1,
        { before: before.length, after: lastValue(sent).slots.length });

  // a new epoch reloads from Python
  render(w, { days, times, mode: "edit", epoch: 1, selected: ["2026-08-01 18:00"], counts: {}, names: {}, colors: {}, best: [], people: [], me_slots: [] });
  check("new epoch reloads selection", cell(w, 0, 0).classList.contains("on") && !cell(w, 2, 2).classList.contains("on"));
}

/* ---------------- view mode ---------------- */
console.log("view mode");
{
  const { sent, w } = boot();
  render(w, {
    days, times, mode: "view", epoch: 0, selected: [],
    counts: { "2026-08-01 19:00": 2, "2026-08-02 19:00": 1 },
    names: { "2026-08-01 19:00": ["Alice", "Bob"], "2026-08-02 19:00": ["Alice"] },
    colors: { Alice: "#e4572e", Bob: "#2e86ab" },
    best: ["2026-08-01 19:00"],
    people: ["Alice", "Bob"], me_slots: [],
  });
  check("grid is in view mode", !!w.document.querySelector(".grid.view"));
  const c = cell(w, 0, 2);
  // jsdom rewrites hex to rgb(), so match on that plus the hard 50% stop
  check("overlap cell gets a two-colour gradient with hard stops",
        c.style.background.includes("rgb(228, 87, 46) 50%") &&
        c.style.background.includes("rgb(46, 134, 171) 50%"), c.style.background);
  check("overlap cell shows the count", c.querySelector(".n").textContent === "2");
  check("best slot outlined", c.classList.contains("best"));
  check("tooltip names who is free", c.title.includes("Alice, Bob"), c.title);
  check("single-person cell has no count badge", cell(w, 1, 2).querySelector(".n").textContent === "");
  check("empty cell dimmed", cell(w, 2, 0).classList.contains("dim"));
  check("legend lists both people", w.document.querySelectorAll(".legend .item").length === 2);
  check("no drag value emitted in view mode", lastValue(sent) === null);

  // empty state
  render(w, { days, times, mode: "view", epoch: 0, selected: [], counts: {}, names: {}, colors: {}, best: [], people: [], me_slots: [] });
  check("empty state message", w.document.querySelector(".empty") !== null);
}

/* ---------------- dark theme ---------------- */
console.log("theme");
{
  const { w } = boot();
  render(w, { days, times, mode: "edit", epoch: 0, selected: [], counts: {}, names: {}, colors: {}, best: [], people: [], me_slots: [] },
         { base: "dark", backgroundColor: "#0e1117", secondaryBackgroundColor: "#20242d", textColor: "#e8eaf0" });
  check("dark theme vars applied",
        w.document.documentElement.style.getPropertyValue("--bg") === "#0e1117");
}

console.log(failures ? `\n${failures} FAILURES` : "\nAll grid tests passed.");
process.exit(failures ? 1 : 0);
