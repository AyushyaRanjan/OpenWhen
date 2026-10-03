# Letting your friend use Open When from their phone

This guide shows you how to let one person — your friend — open the Open When
app on their phone, over the internet, without ever putting your laptop on the
open web.

The short version: your laptop keeps the app locked to itself, and **Tailscale**
acts like a private, invisible cable between your laptop and your friend's phone.
Only devices on your private Tailscale network can reach the app. Nobody else can.

Take your time. Nothing here is permanent, and at the end there are simple ways
to switch it all off again.

---

## Read this first: what this does and does not do

- The app itself still runs the same way. It stays on `127.0.0.1:8000`, which
  means *only this laptop* can talk to it directly. We never change that.
- Tailscale is what reaches in from the outside. It is opt-in and it is the one
  part of this setup that uses the internet. The rest of Open When is unchanged
  and still works with no internet at all.
- Because the friend you share with gets access to the whole app on your laptop,
  they could also open the admin page at `/admin.html`. The admin page is
  protected by the passcode in your `config.json`. **Use a long, private
  passcode** before you share anything. Never tell your friend the passcode.
- Never enable `tailscale funnel`. Funnel puts the app on the public internet for
  anyone to find. This guide only uses `tailscale serve`, which stays private.

If any of that worries you, that's fair — skip to the end of this file for the
"Turn it all off" section, which undoes everything.

---

## How it works, in one picture

```
  Your friend's phone
          |
          |   (Tailscale: an encrypted private tunnel
          |    that only your two devices can use)
          v
  Your laptop  --->  tailscale serve  --->  http://127.0.0.1:8000
                                                 (the app, still locked to this laptop)
```

`tailscale serve` also gives you a real HTTPS address, which matters: phones only
allow installing a web app and using the microphone over a secure `https://`
connection. Tailscale takes care of the certificate for you.

---

## Before you start

You need:

- Open When already working on your laptop (you can open `http://127.0.0.1:8000`
  in a browser on the laptop).
- A Tailscale account (free) and the Tailscale app installed on the laptop.
- A strong `admin_passcode` in your `config.json`.
- Your friend's email address, so you can invite or share with them.

You do **not** need to change any code, forward any ports, or touch your router.

---

## Part 1 — On your laptop

### Step 1: Start the app

Open **PowerShell**, then run these three lines one at a time:

```powershell
Set-Location "C:\Disk E\Code\openWhen"
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave this window open. As long as it is open, the app is running. When you want
to stop the app, click in the window and press **Ctrl + C**.

Check it worked: open `http://127.0.0.1:8000` in the laptop's browser. You should
see a warm greeting over the question "How are you feeling?" — that's the home screen.

### Step 2: Install and sign in to Tailscale

If Tailscale is not installed yet, install it from the Windows Package Manager:

```powershell
winget install --id Tailscale.Tailscale
```

(You can also download it from <https://tailscale.com/download/windows>. The
download page is fine to visit for the installer; the app itself does not send
your Open When content anywhere.)

After it installs, it will ask you to sign in. Use your own account. When you are
done, the Tailscale icon in the system tray should say "Connected". If it does
not, open the Tailscale window and click **Connect** (or run `tailscale up`).

### Step 3: Turn on MagicDNS and HTTPS

This is a one-time setting on the Tailscale website.

1. Go to <https://login.tailscale.com/admin/dns> and sign in.
2. Turn on **MagicDNS** if it is off.
3. Turn on **HTTPS Certificates**. Tailscale will ask you to confirm; say yes.
   This is what gives you a trusted padlock address.

### Step 4: Put the app behind HTTPS

Back in PowerShell (you can open a second window), run:

```powershell
tailscale serve --bg 8000
```

This tells Tailscale: "anything that comes in over my private network should go
to the app on port 8000." It runs in the background, so you can close the window.

If you are on an older Tailscale, the same thing with the long form is:

```powershell
tailscale serve https / http://127.0.0.1:8000
```

Check it worked:

```powershell
tailscale serve status
```

A correct result looks something like this (your laptop and tailnet names will
be different):

```
https://your-laptop.your-tailnet.ts.net (tailnet only)
|-- / proxy http://127.0.0.1:8000
```

### Step 5: Find your HTTPS address

That `https://your-laptop.your-tailnet.ts.net` line **is** your address. Three
ways to see it:

- `tailscale serve status` (just above).
- Open the admin console at <https://login.tailscale.com/admin/machines> and
  look at your laptop's name; the full name is the part before `.ts.net`.
- In PowerShell, `tailscale status` shows your laptop's short name.

Write the full address down. It always starts with `https://` and ends with
`.ts.net/`. Do not use `http://` and do not use an IP address; the padlock and
the phone microphone depend on that exact name.

---

## Part 2 — Share it with your friend

There are two ways. Pick one.

### Option A: Invite your friend to your network

This lets them see your whole private network. Simpler, but broader.

1. Go to <https://login.tailscale.com/admin/users>.
2. Choose **Invite external users** (sometimes shown as **Invite**).
3. Enter your friend's email and send the invite.
4. Your friend gets an email. They click the link, create a free Tailscale
   account with that same email, and accept.

### Option B: Share just this laptop (recommended)

This gives your friend access to this one laptop only, nothing else on your
network. It is the tidier choice.

1. Go to <https://login.tailscale.com/admin/machines>.
2. Find your laptop in the list, open the **...** menu next to it, and choose
   **Share**.
3. Enter your friend's email and send the share.
4. Your friend gets an email. They click it, sign in, and **accept the share**.
   Until they accept, they still cannot reach the app.

If they say "it says I don't have access," the usual fix is that they have not
clicked **Accept** on the share yet.

---

## Part 3 — On your friend's phone

Send your friend the `https://...ts.net/` address from Step 5. Then they:

1. Install **Tailscale** from the Google Play Store (Android) or the App Store
   (iPhone). It is free.
2. Open Tailscale and sign in with the **same email** you sent the invite or
   share to.
3. On Android, tap the switch to turn Tailscale on; a small key/VPN icon appears
   at the top. On iPhone, tap the toggle; a **VPN** label appears in the status
   bar. If they have never used a VPN before, the phone will ask permission once.
4. Open their normal browser (Chrome on Android, Safari on iPhone) and go to
   your `https://...ts.net/` address.

They should see the same warm home screen you see on the laptop.
If they do, you are done.

---

## Part 4 — Add it to the Home screen

Once it opens, it can live on their phone like a real app.

### Android (Chrome)

1. Open the address in **Chrome**.
2. Tap the **three dots** menu (top right).
3. Tap **Add to Home screen** (Chrome may instead say **Install app** — either
   works; "Install app" gives the fuller app experience).
4. Tap **Add** / **Install**, then confirm the name **Open When**.

### iPhone (Safari)

It must be **Safari** for this part; Chrome on iPhone cannot add it.

1. Open the address in **Safari**.
2. Tap the **Share** button (the square with an arrow pointing up, at the bottom
   or top of the screen).
3. Scroll down and tap **Add to Home Screen**.
4. Name it **Open When** and tap **Add**.

Now there is an Open When icon on the phone's home screen. Tapping it opens the
app on its own, without the browser address bar.

---

## Part 5 — Check that it really is installable

The app is set up to be installable. Here is how to confirm, from easiest to
most technical.

On the phone, after adding it to the Home screen:

- It opens **without** the browser's address bar (this is called "standalone").
- The icon shows the Open When picture, not a plain letter.
- If you briefly turn the phone's Wi-Fi/data off and open it, the screen still
  appears (a cached copy); it just cannot load new messages until you are back
  online.

On the laptop, in desktop **Chrome** (this is optional, for the curious):

1. Open the app at your `https://...ts.net/` address.
2. Press **F12** to open developer tools.
3. Go to **Application** → **Manifest**. You should see the name "Open When" and
   two icons (192 and 512).
4. Go to **Application** → **Service Workers**. You should see `/sw.js` with
   the status **activated**.

If Chrome offers an "Install" icon in the address bar, that is the surest sign
it is installable.

---

## Part 6 — Troubleshooting the five most common problems

### 1. "I can't reach the page" (the browser spins or errors)

Work through these in order:

1. Is the app window still open on the laptop? If you closed PowerShell, the app
   stopped. Start it again (Part 1, Step 1).
2. On the laptop, run `tailscale serve status`. If it says "No serve config",
   run `tailscale serve --bg 8000` again.
3. Is Tailscale **on** on the friend's phone? Ask them to check the toggle and
   look for the VPN/key icon.
4. Did they **Accept** the share or invite in their email? An unaccepted share
   does not let them in.
5. Are they using the exact `https://...ts.net/` address, including the `.ts.net`
   part? An IP address will not work.
6. Restart Tailscale on both sides (right-click the tray icon → exit, then open
   it again; on the phone, toggle Tailscale off and on).

### 2. "The microphone is blocked" (voice notes won't record)

1. The microphone only works on `https://`. Confirm the address starts with
   `https://` and shows a padlock. If not, go back to Step 5.
2. The friend must tap the record button themselves; browsers ignore microphone
   requests that are not started by a tap.
3. If they tapped **Block** by accident, they need to undo it:
   - **Android Chrome:** open the site → tap the padlock/tune icon near the
     address → **Permissions** → **Microphone** → **Allow** → reload.
   - **iPhone Safari:** Settings app → **Safari** → **Microphone** (and
     **Settings → Privacy & Security → Microphone**) → make sure Safari is on,
     then reload the page.
4. Check the phone is not on a headset that has no microphone, and that no other
   app (a call, a voice recorder) is holding the mic.

### 3. "The voice notes won't play"

1. On iPhone, the little side **mute switch** silently blocks web audio. Flip it
   to unmute.
2. Turn the volume up, and make sure the phone is not in silent/Do-Not-Disturb.
3. Tap the play button directly — browsers are not allowed to start sound on
   their own.
4. iPhone Safari cannot play some audio formats. If a note will not play in one
   browser, ask them to try **Safari on iPhone** or **Chrome on Android**.
5. Reload the page once; a half-loaded audio player sometimes needs a fresh try.

### 4. "There's an HTTPS warning" or "Not secure"

1. A brand-new Tailscale HTTPS certificate can take a minute to be issued. Wait
   a minute and reload.
2. Check that **HTTPS Certificates** is switched on (Part 1, Step 3).
3. Make sure the address is `https://`, not `http://`, and that it ends in
   `.ts.net/`. The padlock is tied to that exact name.
4. Make sure the phone's clock is set to "automatic" (a wrong clock breaks
   certificates).
5. Make sure Tailscale is connected on both devices; the certificate only
   resolves over the Tailscale network.

If you still see a warning, you can force a fresh certificate on the laptop with
`tailscale cert your-laptop.your-tailnet.ts.net`, then reload.

### 5. "It's showing an old version of the app"

The app saves a copy of itself on the phone so it opens quickly. Occasionally
that copy is stale.

1. First, just close the Open When icon completely (swipe it away from the
   recent-apps list) and open it again.
2. In the browser version, pull down to refresh, or hold the reload button.
3. If it is still old, clear just this site's data:
   - **Android Chrome:** tap the padlock/tune icon → **Cookies and site data** →
     **Manage** → delete the site's data → reload.
   - **iPhone Safari:** Settings app → **Safari** → **Advanced** → **Website
     Data** → find the `...ts.net` entry → **Delete** → reload.
4. On the laptop's desktop browser, a "hard refresh" (**Ctrl + Shift + R**) often
   does it.
5. If you, the developer, changed the app's files, the fix is to update the
   cache name in `static/sw.js` (change `openwhen-shell-v1` to `-v2`) and run
   `tailscale serve reset` followed by `tailscale serve --bg 8000` so phones pick
   up the new version.

---

## Part 7 — Turn it all off

You can undo everything, in this order:

1. In PowerShell: `tailscale serve reset` — stops sharing the app over HTTPS.
2. On <https://login.tailscale.com/admin/machines>, remove the share (find the
   laptop's **...** menu → **Share** → remove) or remove an invited user from
   <https://login.tailscale.com/admin/users>.
3. On the phone, the friend can turn Tailscale off, or uninstall it.
4. In the app window on the laptop, press **Ctrl + C** to stop the server.

The app is now back to being completely private to the laptop.

---

## Alternative: Cloudflare Tunnel with Cloudflare Access

This is a different way to reach the app from a phone. It is genuinely more
convenient for the other person, but it fits Open When's "everything stays on
your laptop" spirit less well, so treat it as a fallback.

**What it is:** `cloudflared` runs on your laptop and makes an outbound
connection to Cloudflare. Cloudflare gives you an HTTPS address. **Cloudflare
Access** then puts a login in front of it, so only the email you allow can get
in. Uvicorn still stays on `127.0.0.1`.

**The short version of the steps:**

1. Install `cloudflared` (for example `winget install --id Cloudflare.cloudflared`).
2. Do **not** use a "quick tunnel" (`cloudflared tunnel --url http://localhost:8000`).
   It creates a random public address with **no login at all** — anyone who
   guesses the link gets in. It is only for quick tests.
3. Use a named tunnel with your own domain on Cloudflare:
   `cloudflared tunnel login`, then `cloudflared tunnel create openwhen`, then
   `cloudflared tunnel route dns openwhen when.yourdomain.com`, then run
   `cloudflared tunnel run openwhen`.
4. In the Cloudflare **Zero Trust** dashboard, add an **Access application** for
   `when.yourdomain.com` with a policy that **allows only your friend's email**
   and a login method such as **One-time PIN**. Now Cloudflare asks for a code
   sent to their email before the app loads.
5. Optionally install it as a Windows service (`cloudflared service install`) so
   it starts automatically.

### Tailscale vs Cloudflare — the tradeoffs

| | Tailscale `serve` | Cloudflare Tunnel + Access |
| --- | --- | --- |
| Friend installs an app | Yes, Tailscale | No, just a browser |
| Who can reach it | Only devices on your private tailnet | The public internet, behind an email login |
| Where the traffic can be seen | Device to device (WireGuard); only your two devices hold the keys | Cloudflare's edge terminates HTTPS, so Cloudflare can see traffic in transit |
| Needs a domain name | No | Yes, a domain on Cloudflare |
| Account needed | Free Tailscale account | Free Cloudflare account (plus a domain) |
| Network exposure | Small; not publicly discoverable | Bigger; the endpoint is public and only the login guards it |
| Fits Open When's local-first rule | Closer | Further away |
| Offline behaviour | App still works offline on the laptop | Requires the internet |

**If you are not sure, use Tailscale.** It keeps the app on your private network
and does not hand your content to another company's edge servers.

---

## A few privacy notes to keep in mind

- Sharing with your friend means they can reach **everything** the app serves on
  your laptop, including the admin page at `/admin.html`. Set a long, private
  `admin_passcode` first, and never share it.
- Voice notes live under `/media/` and are reachable by anyone on your tailnet.
  Keep your tailnet invite/share limited to your friend.
- Never commit your real `config.json`. It holds your passcode and your helper's
  phone number. The file is already ignored by git; keep it that way.
- Avoid `tailscale funnel` and Cloudflare "quick tunnels": both expose the app to
  the public internet.
- When in doubt, run `tailscale serve reset` (and stop the server) to go back to
  laptop-only.

That's everything. If something here doesn't match what you see on screen, stop
and ask rather than guessing — it is better to leave the app private than to
expose it by accident.
