"""
When Can We Meet? — a tiny shared scheduler for a group call.

Everything is shown in Mountain Time (America/Denver) no matter where the
person filling it in happens to be, so there is exactly one clock to argue
about.
"""

from __future__ import annotations

import json
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

_grid = components.declare_component(
    "availability_grid", path=str((Path(__file__).parent / "frontend").resolve())
)


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
def today_mt() -> date:
    return datetime.now(MT).date()


def build_days(start: date, num_days: int) -> list[dict]:
    t = today_mt()
    out = []
    for i in range(num_days):
        d = start + timedelta(days=i)
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
        out.append({
            "value": f"{h:02d}:{m:02d}",
            "label": pretty_time(h, m),
            "major": m == 0,
        })
        minute += SLOT_MINUTES
    return out


def pretty_time(h: int, m: int) -> str:
    suffix = "am" if h < 12 else "pm"
    hour12 = h % 12 or 12
    return f"{hour12}:{m:02d} {suffix}" if m else f"{hour12} {suffix}"


def slot_key(day: str, tvalue: str) -> str:
    return f"{day} {tvalue}"


def slot_dt(key: str) -> datetime:
    return datetime.strptime(key, "%Y-%m-%d %H:%M").replace(tzinfo=MT)


def fmt_span(day: str, start_value: str, minutes: int, tz: ZoneInfo | None = None) -> str:
    begin = slot_dt(slot_key(day, start_value))
    finish = begin + timedelta(minutes=minutes)
    if tz:
        begin, finish = begin.astimezone(tz), finish.astimezone(tz)
    same_day = begin.date() == finish.date()
    head = begin.strftime("%a %b ") + str(begin.day)
    a = pretty_time(begin.hour, begin.minute)
    b = pretty_time(finish.hour, finish.minute)
    return f"{head}, {a} – {b}" if same_day else f"{head}, {a} – {b} (+1 day)"


# --------------------------------------------------------------------------- #
# data helpers
# --------------------------------------------------------------------------- #
def get_settings(data: dict) -> dict:
    s = dict(data.get("settings") or {})
    s.setdefault("title", "Group call")
    s.setdefault("num_days", 14)
    s.setdefault("start_hour", 8)
    s.setdefault("end_hour", 22)
    s.setdefault("start_date", today_mt().isoformat())
    s.setdefault("pin_start", False)
    return s


def effective_start(settings: dict) -> date:
    stored = date.fromisoformat(settings["start_date"])
    if settings.get("pin_start"):
        return stored
    return max(stored, today_mt())


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
            raw.append({
                "date": day["date"], "start_idx": i, "end_idx": i + slots_needed - 1,
                "free": frozenset(free), "keys": keys,
            })

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
# session bootstrapping
# --------------------------------------------------------------------------- #
data = storage.load_data()
settings = get_settings(data)

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

days = build_days(effective_start(settings), int(settings["num_days"]))
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
# sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.subheader("Event settings")
    st.caption("These apply to everyone. Change them once, at the start.")

    with st.form("settings_form"):
        title = st.text_input("What's the meeting called?", value=settings["title"])
        num_days = st.slider("How many days ahead?", 3, 28, int(settings["num_days"]))
        hour_range = st.slider("Hours shown each day (MT)", 0, 24,
                               (int(settings["start_hour"]), int(settings["end_hour"])))
        pin_start = st.checkbox(
            "Pin the first day", value=bool(settings.get("pin_start")),
            help="Off: the grid always starts today and rolls forward. On: it stays on the date below.",
        )
        pinned = st.date_input("First day", value=date.fromisoformat(settings["start_date"]))
        if st.form_submit_button("Save settings", use_container_width=True):
            if hour_range[0] >= hour_range[1]:
                st.error("The end hour has to be after the start hour.")
            else:
                first_day = pinned if (pin_start and isinstance(pinned, date)) else today_mt()
                data["settings"] = {
                    "title": title.strip() or "Group call",
                    "num_days": int(num_days),
                    "start_hour": int(hour_range[0]),
                    "end_hour": int(hour_range[1]),
                    "pin_start": bool(pin_start),
                    "start_date": first_day.isoformat(),
                }
                storage.save_data(data)
                st.rerun()

    st.divider()
    st.subheader("Backup")
    st.caption(f"Saving to: **{storage.backend_name()}**")
    st.download_button(
        "Download a copy",
        data=json.dumps(data, indent=2),
        file_name="availability-backup.json",
        mime="application/json",
        use_container_width=True,
    )
    restore = st.file_uploader("Restore from a backup", type="json")
    if restore is not None and st.button("Restore this file", use_container_width=True):
        try:
            storage.save_data(json.loads(restore.read().decode("utf-8")))
            st.success("Restored.")
            st.rerun()
        except Exception as exc:
            st.error(f"That file didn't load: {exc}")

    if people:
        st.divider()
        if st.button("Clear everyone's answers", use_container_width=True):
            st.session_state.pending_delete = "__all__"
        if st.session_state.pending_delete == "__all__":
            st.warning("This wipes every response. There's no undo.")
            c1, c2 = st.columns(2)
            if c1.button("Wipe it", use_container_width=True):
                data["people"] = {}
                storage.save_data(data)
                st.session_state.pending_delete = None
                st.rerun()
            if c2.button("Keep it", use_container_width=True):
                st.session_state.pending_delete = None
                st.rerun()

# --------------------------------------------------------------------------- #
# header
# --------------------------------------------------------------------------- #
st.title(settings["title"])
st.caption(
    f"All times are **Mountain Time** ({datetime.now(MT):%b %d, %I:%M %p} MT right now). "
    f"Paint when you're free, hit save, and the group view updates for everyone."
)

st.radio("Section", [VIEW_ME, VIEW_GROUP], key="view", horizontal=True, label_visibility="collapsed")

# --------------------------------------------------------------------------- #
# view: fill in my times
# --------------------------------------------------------------------------- #
if st.session_state.view == VIEW_ME:
    if st.session_state.just_saved:
        st.success(f"Saved {st.session_state.just_saved}. Switch to “See everyone” to compare.")
        st.session_state.just_saved = None

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
                "updated": datetime.now(MT).isoformat(timespec="seconds"),
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
        st.info("No answers yet. Head to “Fill in my times” and go first.")
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

    # ---- headline ---------------------------------------------------------- #
    if not windows:
        st.error(
            f"There is no {length_label} block where even one of these people is free. "
            "Try a shorter meeting, or a wider hour range in the sidebar."
        )
    else:
        winners = [w for w in windows if w["score"] == top_score]
        missing = sorted(set(participants) - set(winners[0]["free"]))
        headline = "Everyone can make it" if top_score == len(participants) else f"Best so far: {top_score} of {len(participants)}"
        st.subheader(headline + ("" if len(winners) == 1 else f" — {len(winners)} equally good options"))

        for w in winners[:6]:
            gap = sorted(set(participants) - set(w["free"]))
            note = "everyone free" if not gap else "missing " + ", ".join(gap)
            span = "" if w["span_minutes"] <= minutes_needed else f"  ·  window open {w['span_minutes'] // 60}h{w['span_minutes'] % 60 or ''}"
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

        # ---- pick one and take it away ------------------------------------- #
        st.write("")
        choices = winners[:10] + [w for w in windows if w["score"] < top_score][:10]
        labels = [
            f"{fmt_span(w['date'], w['start_value'], minutes_needed)}  ({w['score']}/{len(participants)})"
            for w in choices
        ]
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

    # ---- the overlap grid -------------------------------------------------- #
    st.write("")
    st.markdown("#### Everyone's times together")
    availability_grid(
        days=days, times=times, mode="view", epoch=st.session_state.epoch, key="grid_view",
        counts=counts, names=names_at, colors=colors, best=best_keys, people=participants,
    )

    # ---- roster ------------------------------------------------------------ #
    st.write("")
    st.markdown("#### Who's answered")
    st.caption("Click Edit on your own row to change your times.")
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
        if row[3].button("Edit", key=f"edit_{person}", use_container_width=True):
            start_editing(person)
            st.rerun()
        if row[4].button("Remove", key=f"del_{person}", use_container_width=True):
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
