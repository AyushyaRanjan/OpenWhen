# Open When...

Open When... is a small, private web app that keeps a few kind words close by
for someone who is having a hard day. When they say how they feel, it shows them
a message or voice note from someone who loves them, or one of their own logged
wins. It runs entirely on one laptop and talks to no company's servers.

It is built to be read and changed by one person, not scaled. If you are looking
for a product, this is not it. If you are looking for something warm, small and
yours, it might be.

## What it is, and who it is for

The person who uses it is **one specific friend** who often feels low or alone.
They open it on their phone or laptop, tap how they feel, and get back something
human that already existed — a note from a parent, a voice memo from a best
friend, a small win they logged themselves. The app never invents closeness; it
just helps them find what is already there.

The other person in the picture is a **helper** (you): someone who writes the
messages, records the voice notes, and sets up the app. You run it, you own it,
and you decide what it says.

## Honest limits

Read these before you expect too much.

- **This is a comfort tool, not therapy.** It does not diagnose, treat, or
  replace a real person or a professional.
- **It is not a crisis service.** It has a basic safety check (described below),
  but that check can miss things. If someone is in danger, they should call a
  crisis line or emergency services. Do not rely on this app as a safety net.
- **The local AI models are small and less fluent than large cloud models.** The
  app is designed to work with models that fit on an ordinary laptop. They can
  be awkward, repetitive, or clumsy. They are meant to gently introduce notes
  that a human wrote, not to write the notes themselves.
- **The safety check is keyword-based** (a model pass exists but is off by
  default). Keyword filters are a minimum safeguard. They can miss context and
  code words, and they can fire on things that are not a crisis. They are not
  clever, and they are not a guarantee.

If those limits are not acceptable for the person you have in mind, that is a
reasonable thing to feel. This app may still help as one small thing among
others, but it should not be the only thing.

## How it works, in plain words

There are only a few moving parts.

- **One Python server** (FastAPI) runs on your laptop, bound to `127.0.0.1` so
  only this machine can reach it. It serves both the web pages and a small JSON
  API.
- **One SQLite file** (`comfort.db`) stores everything: each message and win,
  the sender's name or note text, an optional voice recording, and a numeric
  "embedding" of the text. There is no database server to install.
- **Ollama**, a local model runner, provides two things: a **chat model** that
  writes the short warm lead-in and the tiny step, and an **embedding model**
  that turns text into vectors for search.
- **Search is simple math.** Each message *and each win* is stored as a vector.
  When the friend says how they feel, the app embeds that feeling and finds the
  closest items using cosine similarity (numpy). If nothing is close enough, it
  falls back to the two most recent messages, and to one of the friend's own
  wins, so there is always something kind to show.
- **The frontend is plain HTML, CSS and JavaScript** — no framework and no build
  step. It is a PWA (a web app that can be added to the phone's home screen),
  with a hand-written manifest and service worker. The service worker caches
  only the static shell; it never caches feelings, messages, or voice notes.
- **The AI's words come from editable prompt files** in `prompts/`. You can
  change the tone without touching code.

In one line: the server reads a feeling, does a safety check, searches the
database for something close, asks the local model for one warm sentence to
introduce it, and sends it back.

## Why a local, open-source approach

- **Privacy.** The messages, the voice notes and what the friend types never
  leave the laptop. There is no cloud API, no analytics, no telemetry, and no
  external fonts or scripts. The prompts and the crisis message are all plain
  text you can read.
- **Zero running cost.** Once it is set up, it costs nothing to run. No
  subscription, no per-request fees.
- **Swappable models.** The chat and embedding models are named in `config.json`
  and can be changed to any model your laptop can run. A small tool,
  `tools/compare_models.py`, lets you try several on the same inputs and read
  the results side by side.
- **Full control over safety rules and tone.** The crisis phrase list
  (`safety_phrases.json`) and the AI instructions (`prompts/`) are files you can
  edit. Nobody else decides how it speaks to your friend.
- **Works offline.** Everything runs locally, so it keeps working with no
  internet at all.

## Setup from scratch on Windows

You will need Windows, Python, and Ollama. Roughly 4–6 GB of free disk space for
the models, and an internet connection only for the initial downloads.

### 1. Install Python

Install Python 3.11 or newer from <https://www.python.org/downloads/windows/>
(tick **Add Python to PATH** during install), or with the package manager:

```powershell
winget install --id Python.Python.3.12
```

Check it worked by opening PowerShell and running:

```powershell
python --version
```

### 2. Put the project somewhere and make a virtual environment

Put the `openWhen` folder where you like, for example `C:\Disk E\Code\openWhen`.
Then, in PowerShell:

```powershell
Set-Location "C:\Disk E\Code\openWhen"
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell refuses to run the activation script, run this once for the
current window and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 3. Install Ollama and pull the models

Install Ollama for Windows from <https://ollama.com/download> or:

```powershell
winget install --id Ollama.Ollama
```

Then pull one embedding model and one chat model. The example config uses these:

```powershell
ollama pull nomic-embed-text
ollama pull qwen2.5:3b
```

`gemma2:2b` is a lighter alternative if three billion parameters is too much for
your machine; set `chat_model` to whichever you pulled. You can check what you
have with `ollama list`.

### 4. Make your config

```powershell
Copy-Item config.example.json config.json
```

Open `config.json` in any text editor and fill in the values (they are described
in the next section). At minimum, set `friend_name`, `helper_name`,
`helper_phone`, and a private `admin_passcode`. Then start the app:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave that window open while you use the app. Press **Ctrl + C** to stop it.

### 5. Open it

- The friend's app: <http://127.0.0.1:8000>
- The admin page (to add messages and voice notes): <http://127.0.0.1:8000/admin.html>

To let your friend use it on their own phone, see `docs/PHONE_ACCESS.md`.

## Configuration

All settings live in `config.json`. The app will start from
`config.example.json` if `config.json` is missing, but you should make your own.

| Key | What it does |
| --- | --- |
| `chat_model` | The Ollama chat model that writes the lead-in and the tiny step. Must match a name from `ollama list`. |
| `embed_model` | The Ollama embedding model used for search. `nomic-embed-text` is the default. |
| `ollama_url` | Where Ollama is listening. Keep it local (`http://127.0.0.1:11434`). |
| `friend_name` | Shown in the app's greeting. |
| `helper_name` | The trusted person the friend would want in a hard moment. Appears in the crisis message. |
| `helper_phone` | The helper's phone number, used to build a tap-to-call link. Keep the real one out of git. |
| `moods` | The list of feeling buttons shown on the home screen. |
| `min_match_score` | How close a message has to be to count as a match (0 to 1). Lower means it shows more, looser matches. `0.3` is a reasonable default. |
| `keep_alive` | How long Ollama keeps a model in memory after a request, e.g. `"5m"`. Longer is faster but uses more RAM. |
| `use_model_safety_check` | **Off by default.** When `true`, a second, model-based crisis check runs in addition to the keyword list. Small local models over-trigger on this, so the keyword list is the real safeguard; leave it `false` unless you have tested it. |
| `admin_passcode` | The passcode for the admin page and admin API routes. **An empty value means admin is switched off, not open.** Use a private value and never commit it. |
| `resting_message` | Optional. The human-written line shown when the server cannot be reached, instead of any "offline" language. Defaults to `We're not offline — you can reach us any time. — your friends`. |
| `health_url` | Optional. The address the watchdog checks. Defaults to `http://127.0.0.1:8000/api/health`. |
| `ntfy_url` | Optional. The base URL of a **self-hosted** ntfy server for watchdog alerts. Defaults to `http://127.0.0.1:8080`. Do not point this at a cloud service. |
| `ntfy_topic` | Optional. The ntfy topic the watchdog posts to. Empty means the watchdog runs silently. |

The frontend is allowed to read only three of these — `friend_name`, `moods`
and the `resting_message` copy — through `GET /api/config`. Everything else,
including the helper's phone number and the passcode, stays on the server.

## Safety and crisis handling

Safety is checked **before** anything else on every endpoint that accepts free
text: `/api/feel`, `/api/step`, `/api/win`, and the admin `POST /api/item`. If
the check trips, the model is **never called** — not for a rewrite, not for a
summary. The app returns a fixed, human-written crisis message instead.

There are two layers.

1. **A keyword and phrase list** (`safety_phrases.json`). Before matching, text
   is tidied up: lowercased, repeated letters collapsed (`heeeelp` → `help`),
   repeated punctuation collapsed, and whitespace squashed. Phrases are matched
   literally, with word boundaries so `die` does not match inside `diet`. This
   layer is fast, local and deterministic — no model is involved.
2. **An optional model check** (`use_model_safety_check`, **off by default**).
   When enabled, the chat model is asked a strict yes/no question about whether
   the message suggests self-harm. Anything unclear, malformed, or failed is
   treated as "no", so the keyword layer is never weakened by a model problem.
   It is off by default because a small local model tends to answer "yes" to
   almost any heavy-sounding text, which would block a contributor's loving
   note. Turn it on only if you have tested it with your own model.

On the contributor's form (`POST /api/item`), if the check trips and the person
is sure their note was meant as comfort rather than written by someone at risk,
they are offered a **"Save my note anyway"** button. That keeps the note without
building an embedding, so still no model is called.

If either layer trips, the response includes a short message pointing to
Tele-MANAS 14416, the helper's phone number, and 112, each as a tap-to-call
link, plus a gentle offer to stay. The crisis text is a literal string written
by a person in `app/safety.py`, never generated by a model.

Two honest things to keep in mind:

- Keyword checks are a **minimum safeguard**. They can miss paraphrases, code
  words, and context; they can also fire on innocent text. Treat them as one
  basic net, not a solution.
- The AI is also instructed never to give medical or mental-health advice, never
  to claim to be human, and never to invent facts or memories that were not in
  its context. Prompts and code enforce this as best they can; small models do
  not always obey, which is another reason not to over-trust the output.

## Saved favourites, and when the server is resting

The friend can save any message they want to keep by tapping the little heart on
its card. Saving is done **on their phone only**: the words are kept in the
phone's own storage and the voice note is copied into the service-worker cache.
Nothing about a favourite is sent to the server, and no favourite is ever shared
across devices.

Whether or not the friend keeps anything, the phone keeps the **last five
messages from loved ones** on hand so the resting screen is never bare. It does
two things: every note it shows them is remembered, and whenever the app opens
while the server is reachable it quietly fetches a few recent notes in the
background (`GET /api/recent`), so there is something to show even if they never
tapped a feeling first. These stay on the phone too. The friend's own wins are
kept out of *this* memory — the resting screen is about other people's words —
but they have their own shelf: every win is logged with a vector so it can match
later, and all of them appear under **Your wins** on the Saved screen, mirrored
onto the phone so the shelf is there with no connection. A win comes back when
the friend taps a feeling or writes something, and now and then when one is the
closest thing to how they feel.

When the phone cannot reach the little server — the laptop is off, asleep, or
the app was stopped — the friend sees a calm screen with the human-written
`resting_message` at the top, by default *"We're not offline — you can reach us
any time. — your friends"*, and their saved and recent messages below, with
voice notes still playable from the cache. There are no error codes and no
browser error page.

A small dot at the bottom of the screen shows, quietly, whether the app is
reachable: a soft green "Here with you" when it is, an amber "Showing what you
saved" when the server cannot be reached.

To try it: load the app while the server is running and leave it on the home
screen for a few seconds (it fetches a few notes in the background), then stop
the server and reload the page on the phone. The recent notes and the resting
line should appear.

Updates apply themselves. The service worker skips waiting, takes over and
reloads the open page once, so an online visit is always enough — there is no
"Refresh" button to find. (It was the old wait-for-a-tap design that once left a
phone running a stale copy.) An already-stuck copy heals on the next online
visit; if a standalone window stays stale, unregister the service worker once in
DevTools → Application.
`docs/PWA_TESTING.md` walks through the full check.

## Watching the server (optional)

`tools/watchdog.py` is a small helper **for you**, not part of the friend's app.
Every five minutes it checks `health_url`, and if the server has stopped
answering it sends one short alert through ntfy. It sends another note when the
server comes back. It only alerts on a change of state, so it will not spam you.

The alert goes to the `ntfy_url` in your config, which defaults to a
self-hosted address on your own network. It is never sent to a cloud service,
and it never contains anything the friend typed, felt, recorded or saved — just
a fixed line and a timestamp.

Run it in a second terminal next to the app:

```powershell
Set-Location "C:\Disk E\Code\openWhen"
.\venv\Scripts\Activate.ps1
python -m tools.watchdog
```

Leave `ntfy_topic` empty to run the checks without sending anything. To test a
single check without waiting, add `--once`.

## Running the tests

The whole test suite runs with pytest (already in the virtual environment):

```powershell
Set-Location "C:\Disk E\Code\openWhen"
.\venv\Scripts\Activate.ps1
python -m pytest -q
```

A correct run ends with something like `112 passed` and no failures. The suite
covers the database, safety checks, search, the API routes, the admin passcode,
the PWA shell, saved favourites and offline behaviour, the watchdog (with the
network mocked), prompt loading, and the model-comparison tool. Many tests use
temporary files or a fake Ollama, so they do not need the real models running.

## How to add your own voice note

This is for the helper. You add a voice note through the admin page; the app
files it away and the friend can then find it when they need it.

You will need the app running (`python -m uvicorn app.main:app --host 127.0.0.1
--port 8000`) and its window kept open.

1. On the laptop, open <http://127.0.0.1:8000/admin.html>.
2. Enter your `admin_passcode`.
3. Choose the kind: **message** (a note from you or someone else) or **win** (a
   win the friend logged).
4. Type the sender's name, the words of the note, and optionally a mood it fits.
5. Use the record button to record a voice note (up to 3 minutes), or attach an
   audio file. Accepted formats are `.webm`, `.mp4`, `.m4a`, `.ogg`, `.mp3` and
   `.wav`, up to 15 MB.
6. Submit. The audio is saved into the `media/` folder and the note is added to
   `comfort.db`.

A few things worth knowing:

- The text you type is safety-checked before anything is saved. If it trips the
  crisis check, the note is not stored and no model is called. You are offered a
  **"Save my note anyway"** button, which keeps the note without a model call.
- The server needs the embedding model reachable to add a note. If Ollama is not
  running, saving a note returns a clear "Ollama unavailable" message instead of
  failing silently.
- Wins logged in the app are embedded on the spot so they can resurface later.
  If a win was logged while Ollama was down it is saved but has no vector; run
  `.\venv\Scripts\python.exe tools\embed_missing.py` once Ollama is back to fill
  those in. It only touches wins, never the deliberately vectorless save-anyway
  notes, and it only logs counts.
- Voice notes and the database are personal. `media/` and `comfort.db` are
  ignored by git, and real recordings should never be committed. If you are
  contributing code, keep your own test audio local.

You can also add notes with the API directly: `POST /api/item` takes a multipart
form with `kind`, `sender`, `text`, an optional `mood`, and an optional `audio`
file. The admin page simply calls this for you.

## A note on privacy, straight up

The app binds to `127.0.0.1` only, calls no external services, and logs no
message bodies, note titles, feelings, or anything else a person typed. The only
moments internet access is involved are the initial model downloads and, if you
choose it, the optional phone-access setup in `docs/PHONE_ACCESS.md`. That setup
is deliberately a separate, opt-in decision, with its privacy tradeoffs written
down there.

If you share the app with someone else, remember they can reach the admin page
on the same address. Keep the `admin_passcode` private.

## Project layout

```
app/            the FastAPI server, safety check, search, and generation
  routes/       the API endpoints
prompts/        the AI instructions, as plain editable text
static/         the frontend: HTML, CSS, JS, PWA manifest and service worker
tests/          the pytest suite
tools/          development helpers and the server watchdog (icon maker, model comparison, win backfill)
docs/           extra guides, including phone access
config.example.json   template for your config.json
safety_phrases.json   the crisis keyword list
```

That is the whole app. It is meant to be small enough to read.
