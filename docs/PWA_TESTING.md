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

## Offline

- [ ] With the app open once, turn off Wi-Fi/data and reload.
- [ ] The home screen still loads (cached shell) instead of a browser error.
- [ ] Feelings and voice notes are **not** expected offline; sending shows the
      friendly "can't reach" line, and the app stays usable.

## Update prompt

Simulate a new version:

1. Make a visible change to a shell file, e.g. add a space or a comment to
   `static/app.css`, and save.
2. On the phone, reload the page. The old page still loads.
3. Reload a second time (or close and reopen).

- [ ] A "fresh version" banner appears.
- [ ] Tapping **Refresh** reloads once and shows the new version.
- [ ] The banner does not trap you: if you ignore it, the app keeps working.

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

## If something fails

Write down what you did, what you expected, and what happened. Check
`docs/PHONE_ACCESS.md` for connection problems, and the browser's DevTools
(Chrome on Android via `chrome://inspect`, Safari on iPhone via the Develop
menu) if you can. Do not log or share the content of any personal message.
