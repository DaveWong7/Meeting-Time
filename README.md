# When can we meet?

A one-page scheduler for picking a group call time. Everyone paints the times
they're free by dragging across a two-week calendar, hits save, and the app
shows the overlap and the best slots. Every time on the site is Mountain Time,
whoever is looking at it.

## Deploy it (about 3 minutes)

1. Push this folder to a new GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub,
   and click **Create app** → **Deploy a public app from GitHub**.
3. Pick the repo, set **Main file path** to `app.py`, deploy.
4. Send your friends the URL.

## Keeping answers around (read this bit)

Streamlit Community Cloud wipes the app's disk whenever it sleeps, restarts, or
redeploys. Answers saved to the local file survive page refreshes and other
visitors, but not a restart. For a call you're planning over a week, add a Gist
backend — then everything lives in your GitHub account instead:

1. Create a secret [Gist](https://gist.github.com) with one file named
   `availability.json` containing `{}`. Copy the ID from the URL
   (`gist.github.com/you/`**`3f9a...`**).
2. Make a [fine-grained token](https://github.com/settings/personal-access-tokens/new)
   with **Gists → Read and write** permission.
3. In your app on Streamlit Cloud: **⋮ → Settings → Secrets**, paste:

   ```toml
   gist_token = "github_pat_..."
   gist_id = "3f9a..."
   ```

The sidebar shows which backend is in use. There's also a **Download a copy**
button and a restore uploader for manual backups either way.

To run it locally instead: `pip install -r requirements.txt && streamlit run app.py`

## How to use it

**Fill in my times** — type your name, then click and drag across the grid.
Dragging over cells you already picked erases them. Clicking a date header
fills that whole day; clicking a time on the left fills that time across every
day. **Evenings only** gives you a rough starting point to adjust. Save when
you're done.

**See everyone** — the grid stacks everybody's answers: each person has a
colour, darker cells mean more people, and gold outlines mark the best
slots for the meeting length you chose (all of them, if there's a tie). Below
that:

- **Who has to be there?** — untick optional people to see if the picture improves.
- **Meeting length** — 30 min to 2 hours; the app only looks for blocks that long.
- **Show that time in** — converts a chosen slot to anyone's home timezone, for
  the message where you tell people when it is.
- **Download calendar invite** — an `.ics` for the slot you locked in.
- **Who's answered** — click **Edit** on your row to change your times, or
  **Remove** to delete an answer.

Event settings (name, how many days ahead, which hours to show) are in the
sidebar and apply to everyone.

## What's in here

| File | What it does |
| --- | --- |
| `app.py` | The whole app: layout, overlap maths, best-slot search |
| `storage.py` | Reads/writes the shared JSON, local file or Gist |
| `frontend/index.html` | The drag-select calendar (a Streamlit custom component, no build step) |
| `test_app.py` | Headless test of the app: `python test_app.py` |
| `test_grid.js` | Headless test of the calendar: `npm i jsdom && node test_grid.js` |

## Notes

- No accounts, no passwords. Anyone with the link can edit anything, which is
  the point for a group of friends.
- Names are matched case-insensitively, so "sam" and "Sam" are the same person
  and the second save updates the first.
- Times an answer holds outside the currently visible hours are kept, not
  deleted, if you narrow the hour range later.
- Daylight saving is handled: Mountain Time slots convert correctly to other
  zones on either side of a changeover.
