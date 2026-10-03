# Testing the Open When app on a phone

This is a **manual** checklist. The automated tests (`pytest`) check that the
files and markup are right; only a real phone can confirm how it *feels*.

There is nothing sensitive in this file. Never paste the helper's real phone
number, the passcode, or a personal Tailscale address into it.

## Before you start

1. Start the app on the laptop (see `README.md`):

   ```
   Set-Location "C:\Disk E\Code\openWhen"
   .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. On the laptop, check it opens: browse to `http://127.0.0.1:8000`.

3. For install and offline behaviour, the phone must load the app over **HTTPS**
   (that is what `tailscale serve` gives you). Follow `docs/PHONE_ACCESS.md` to
   get the `https://<name>.ts.net` address, then open it in the phone's browser.

   - `http://127.0.0.1:8000` counts as a secure address, so install works on the
     laptop itself. A plain `http://<laptop-ip>:8000` on the phone does **not**.

## First run

- [ ] A soft splash appears briefly, then fades away on its own. It never stays
      stuck.
- [ ] The welcome appears the first time only: three short slides with dots.
- [ ] **Next** advances; the last button says **Get started**.
- [ ] **Skip** closes it immediately.
- [ ] After closing, the home screen greets you by name (or just "Hi.").
- [ ] Reload the page: the welcome does **not** come back.

## Add to Home Screen

Android (Chrome):

- [ ] Shortly after the welcome, a small bottom banner offers to add the app.
- [ ] Tapping **Add** shows the real Chrome install prompt.
- [ ] Accepting installs it; the icon appears and opens without browser chrome.
- [ ] Opening from the icon does **not** show the banner again.

iPhone (Safari):

- [ ] After the welcome, a small card explains **Share → Add to Home Screen**
      (no fake button, because iOS has no install prompt).
- [ ] Adding it to the home screen gives the app an icon.
- [ ] Opening from the icon shows no banner.
- [ ] Dismissing the card with **Not now** means it stays gone on the next visit.

Both:

- [ ] When already running installed (`display-mode: standalone`), no banner
      appears at all.

## Saved favourites and resting

While the server is up:

- [ ] Tap the heart on a message: it fills in and the card is kept.
- [ ] Open **Saved for later** from the home screen: the message is listed there.
- [ ] If it had a voice note, play it from the saved list (it comes from the
      phone's cache the second time).
- [ ] Tap the heart again: the message leaves the saved list.
- [ ] Airplane-mode the phone and reopen the app: the saved messages still
      appear and their voice notes still play.
- [ ] Log a win (**Log a win** on the home screen), then open **Saved for
      later**: it appears under **Your wins**. Airplane-mode and reopen: it is
      still there from the phone's copy.

The phone also quietly remembers the **last five messages from loved ones**, so
the resting screen has something real even before you save anything. It remembers
each note it shows you, and every time the app opens while the server is
reachable it prefetches a few recent notes in the background (`GET /api/recent`).
That means you can check the resting screen without tapping a feeling first.

When the server cannot be reached:

- [ ] Load the app while the server is running and wait a few seconds on the home
      screen so the background prefetch finishes. (If you were already using an
      older version, reload twice, or tap **Refresh** on the "fresh version is
      ready" bar, so the new code is active first.)
- [ ] Stop the app on the laptop, then reload on the phone.
- [ ] A calm screen shows the `resting_message` line — by default **"We're not
      offline — you can reach us any time. — your friends"** — with the recent
      and saved messages below, and no error code and no browser error page.
- [ ] The small dot at the bottom is amber and reads **"Showing what you
      saved"** — noticeable, not alarming.
- [ ] Start the app again and reload: the dot goes back to green
      **"Here with you"** and the home screen returns.

## Offline

- [ ] With the app open once, turn off Wi-Fi/data and reload.
- [ ] The home screen still loads (cached shell) instead of a browser error.
- [ ] The recent and saved messages still appear, and their cached voice notes
      still play.
- [ ] New feelings and new voice notes are **not** expected offline; sending
      shows the friendly "can't reach" line, and the app stays usable.

## Updates apply themselves

The service worker no longer waits for a tap. A new version skips waiting, takes
over and reloads the open page once, so an online visit is always enough. This is
deliberate: a worker that waits forever leaves the friend on an old copy.

Simulate a new version:

1. Make a visible change to a shell file, e.g. add a space or a comment to
   `static/app.css`, and to `static/sw.js` bump `CACHE` (for example
   `openwhen-shell-v7`). The bump is required — it is what tells the browser this
   is a new worker worth installing.
2. On the phone, reload the page while the server is running.

- [ ] The page reloads itself once and shows the new version, with no button to
      tap.
- [ ] Nothing loops: it reloads once per new version, not over and over.

Already stuck on an older copy (for example, before this change shipped)? Open
the app once while the server is running and let it settle; the new worker
installs and reloads the page. If a standalone window still looks stale, open
DevTools → Application → Service Workers → **Unregister**, then reload.

## The little things

- [ ] Typing a crisis phrase (for example, words about not wanting to be here)
      shows the fixed, human-written crisis message with call buttons, and the
      model is never called.
- [ ] The phone's call links open the dialler with the right number.
- [ ] Turning on the device's **Reduce Motion** setting stops the big
      animations (splash, transitions) but nothing disappears.
- [ ] On a notched phone, the bottom footer and banners are not hidden behind
      the home bar.
- [ ] Visiting a made-up address like `/nope` shows the friendly 404 page with a
      **Take me home** button.

## The watchdog (on the laptop, optional)

With the app running and a self-hosted ntfy topic set in `config.json`:

1. In a second terminal, start it: `python -m tools.watchdog --interval 10`.
2. Stop the app on the laptop.
3. Wait for the next check.

- [ ] One alert arrives on your ntfy topic, saying Open When isn't answering.
- [ ] Leaving it stopped does **not** send more alerts on later checks.
- [ ] Start the app again: exactly one "back up" note arrives.
- [ ] With `ntfy_topic` empty, the watchdog runs and logs locally but sends
      nothing. `--once` runs a single check and exits.

## If the browser still shows its own error offline

The app can only appear offline if the service worker is in charge of the page.
A few things can stop that:

- **A hard reload bypasses the service worker on purpose.** Use a normal reload
  (F5 / the reload button), not `Ctrl+Shift+R` or "Empty cache and hard reload".
- **The worker may not have installed yet on the very first visit.** Load the app
  once with the server running and give it a few seconds before stopping the
  server.
- **An older worker can be stuck.** In Chrome, open DevTools → **Application** →
  **Service Workers**, click **Unregister**, then reload once with the server
  running. The next normal reload while stopped should show the resting screen.
- **Plain `http://` on a phone is not a secure address,** so service workers do
  not run there at all. Use the HTTPS address from `docs/PHONE_ACCESS.md`.

## If something fails

Write down what you did, what you expected, and what happened. Check
`docs/PHONE_ACCESS.md` for connection problems, and the browser's DevTools
(Chrome on Android via `chrome://inspect`, Safari on iPhone via the Develop
menu) if you can. Do not log or share the content of any personal message.
