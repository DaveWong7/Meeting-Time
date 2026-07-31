"""Headless smoke test: python -m pytest test_app.py  (or just run this file)."""
import json
import os
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TMP = tempfile.mkdtemp()
os.environ["MEETPICKER_DATA"] = os.path.join(TMP, "availability.json")

from streamlit.testing.v1 import AppTest  # noqa: E402

MT = ZoneInfo("America/Denver")


def _seed():
    today = datetime.now(MT).date()
    d1 = today.isoformat()
    d2 = (today + timedelta(days=1)).isoformat()
    data = {
        "version": 1,
        "settings": {},
        "people": {
            "Alice": {"slots": [f"{d1} 19:00", f"{d1} 19:30", f"{d1} 20:00", f"{d2} 09:00"],
                      "updated": "2026-08-01T10:00:00"},
            "Bob": {"slots": [f"{d1} 19:00", f"{d1} 19:30", f"{d1} 21:00"],
                    "updated": "2026-08-01T10:05:00"},
        },
    }
    with open(os.environ["MEETPICKER_DATA"], "w") as fh:
        json.dump(data, fh)
    return d1, d2


def run(**state):
    at = AppTest.from_file("app.py", default_timeout=30)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def test_empty_start():
    if os.path.exists(os.environ["MEETPICKER_DATA"]):
        os.remove(os.environ["MEETPICKER_DATA"])
    at = run()
    assert at.title[0].value == "Group call"
    at = run(view="See everyone")
    assert any("No answers yet" in i.value for i in at.info)


def test_save_and_group_view():
    d1, _ = _seed()
    at = run(view="Fill in my times", draft=[f"{d1} 19:00", f"{d1} 19:30"])
    at.text_input(key="name_input").set_value("Cara").run()
    assert not at.exception
    [b for b in at.button if b.label == "Save my availability"][0].click().run()
    assert not at.exception
    saved = json.load(open(os.environ["MEETPICKER_DATA"]))
    assert "Cara" in saved["people"], saved["people"].keys()
    assert saved["people"]["Cara"]["slots"] == [f"{d1} 19:00", f"{d1} 19:30"]

    at = run(view="See everyone")
    text = " ".join(m.value for m in at.markdown)
    assert "Alice" in text and "Bob" in text and "Cara" in text
    assert at.subheader, "expected a best-slot headline"
    print("headline:", at.subheader[0].value)
    print("winners:", [m.value for m in at.markdown if "—" in m.value][:4])


def test_settings_change():
    _seed()
    at = run()
    at.sidebar.slider[0].set_value(7).run()
    at.sidebar.button[0].click().run()
    assert not at.exception
    saved = json.load(open(os.environ["MEETPICKER_DATA"]))
    assert saved["settings"]["num_days"] == 7


if __name__ == "__main__":
    test_empty_start()
    test_save_and_group_view()
    test_settings_change()
    print("\nAll smoke tests passed.")
