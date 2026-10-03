/* Open When - friend-facing app. No frameworks, no build step. */

(function () {
  "use strict";

  var $ = function (id) {
    return document.getElementById(id);
  };

  var SHOWN_KEY = "openwhen-shown";
  var SHOWN_LIMIT = 50;
  var WELCOME_KEY = "openwhen-welcome-v1";
  var A2HS_KEY = "openwhen-a2hs-v1";
  var FAV_KEY = "openwhen-favourites-v1";

  var config = { friend_name: "", moods: [] };
  var selectedMood = "";
  var lastQuery = { mood: "", text: "" };
  var lastChallenge = "";
  var shown = new Set();
  // Saved by the friend on this phone only; never sent to the server.
  var favorites = {};

  var deferredPrompt = null;
  var refreshing = false;
  var splashHidden = false;

  // ---------------------------------------------------------------- helpers

  function make(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function readFlag(key) {
    try {
      return localStorage.getItem(key) === "1";
    } catch (e) {
      // Private mode or storage disabled: behave as "not yet", and stay usable.
      return false;
    }
  }

  function writeFlag(key) {
    try {
      localStorage.setItem(key, "1");
    } catch (e) {
      /* storage may be unavailable; the app still works for this visit */
    }
  }

  function loadShown() {
    try {
      var raw = sessionStorage.getItem(SHOWN_KEY);
      if (raw) {
        JSON.parse(raw).forEach(function (id) {
          if (id) shown.add(id);
        });
      }
    } catch (e) {
      /* private mode or bad data: rotation just starts fresh */
    }
  }

  function saveShown() {
    try {
      var ids = Array.from(shown).slice(-SHOWN_LIMIT);
      sessionStorage.setItem(SHOWN_KEY, JSON.stringify(ids));
    } catch (e) {
      /* storage may be unavailable; keep the in-memory set */
    }
  }

  function markShown(ids) {
    ids.forEach(function (id) {
      if (id) shown.add(id);
    });
    saveShown();
  }

  function reachError() {
    return "I can't reach the app right now. It's still here, so please try again in a moment.";
  }

  function post(path, body) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then(function (res) {
      if (!res.ok) throw new Error("request failed");
      return res.json();
    });
  }

  function setScreen(name) {
    ["home", "win", "challenge", "saved"].forEach(function (id) {
      $(id).hidden = id !== name;
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ---------------------------------------------------------------- splash

  function hideSplash() {
    if (splashHidden) return;
    splashHidden = true;
    var splash = $("splash");
    if (!splash) return;
    splash.classList.add("is-hidden");
    window.setTimeout(function () {
      if (splash.parentNode) splash.parentNode.removeChild(splash);
    }, 500);
  }

  // ---------------------------------------------------------------- welcome

  var welcomeIndex = 0;
  var welcomeSlides = [];
  var welcomeDots = [];

  function paintWelcome() {
    welcomeSlides.forEach(function (slide, i) {
      slide.classList.toggle("is-active", i === welcomeIndex);
    });
    welcomeDots.forEach(function (dot, i) {
      dot.classList.toggle("is-active", i === welcomeIndex);
    });
    var last = welcomeIndex === welcomeSlides.length - 1;
    $("welcomeNext").textContent = last ? "Get started" : "Next";
    $("welcomeSkip").hidden = last;
  }

  function openWelcome() {
    welcomeSlides = Array.prototype.slice.call(
      document.querySelectorAll(".welcome-slide")
    );
    welcomeDots = Array.prototype.slice.call(
      document.querySelectorAll(".welcome-dot")
    );
    welcomeIndex = 0;
    paintWelcome();
    $("welcome").hidden = false;
    document.body.classList.add("modal-open");
    $("welcomeNext").focus();
  }

  function closeWelcome() {
    writeFlag(WELCOME_KEY);
    $("welcome").hidden = true;
    document.body.classList.remove("modal-open");
    // Let the welcome settle before the (optional) install nudge appears.
    window.setTimeout(maybePromptInstall, 600);
  }

  function welcomeNext() {
    if (welcomeIndex >= welcomeSlides.length - 1) {
      closeWelcome();
      return;
    }
    welcomeIndex += 1;
    paintWelcome();
  }

  // ------------------------------------------------------- add to home screen

  function isStandalone() {
    return (
      (window.matchMedia &&
        window.matchMedia("(display-mode: standalone)").matches) ||
      window.navigator.standalone === true
    );
  }

  function isIOS() {
    var ua = window.navigator.userAgent || "";
    var iOSDevice = /iPad|iPhone|iPod/.test(ua);
    // Newer iPads report as Macintosh but support touch; treat them as iOS too.
    var iPadDesktop = ua.indexOf("Macintosh") !== -1 && "ontouchend" in document;
    return iOSDevice || iPadDesktop;
  }

  function showInstallBanner(kind) {
    if (isStandalone() || readFlag(A2HS_KEY)) return;

    var action = $("a2hsAction");
    if (kind === "android") {
      $("a2hsTitle").textContent = "Keep this close";
      $("a2hsText").textContent =
        "Add Open When to your home screen so it is always one tap away.";
      action.hidden = false;
      action.textContent = "Add";
    } else {
      $("a2hsTitle").textContent = "Keep this close";
      $("a2hsText").textContent =
        "Tap Share, then choose Add to Home Screen.";
      action.hidden = true;
    }
    $("updateBanner").hidden = true;
    $("a2hs").hidden = false;
  }

  function dismissInstall() {
    writeFlag(A2HS_KEY);
    $("a2hs").hidden = true;
  }

  function maybePromptInstall() {
    if (isStandalone() || readFlag(A2HS_KEY)) return;
    if (deferredPrompt) {
      showInstallBanner("android");
    } else if (isIOS()) {
      showInstallBanner("ios");
    }
  }

  function installNow() {
    if (!deferredPrompt) {
      dismissInstall();
      return;
    }
    var prompt = deferredPrompt;
    deferredPrompt = null;
    prompt.prompt();
    Promise.resolve(prompt.userChoice).then(dismissInstall, dismissInstall);
  }

  // ------------------------------------------------------- service worker

  function showUpdateBanner() {
    $("a2hs").hidden = true;
    $("updateBanner").hidden = false;
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;

    window.addEventListener("load", function () {
      navigator.serviceWorker
        .register("/sw.js")
        .then(function (reg) {
          if (reg.waiting && navigator.serviceWorker.controller) {
            showUpdateBanner();
          }
          reg.addEventListener("updatefound", function () {
            var installing = reg.installing;
            if (!installing) return;
            installing.addEventListener("statechange", function () {
              if (
                installing.state === "installed" &&
                navigator.serviceWorker.controller
              ) {
                showUpdateBanner();
              }
            });
          });
        })
        .catch(function () {
          /* offline support is a bonus; the app still works without it */
        });
    });

    navigator.serviceWorker.addEventListener("controllerchange", function () {
      if (refreshing) window.location.reload();
    });
  }

  function reloadForUpdate() {
    if (refreshing) return;
    refreshing = true;
    if (!("serviceWorker" in navigator)) {
      window.location.reload();
      return;
    }
    navigator.serviceWorker
      .getRegistration()
      .then(function (reg) {
        if (reg && reg.waiting) {
          reg.waiting.postMessage({ type: "SKIP_WAITING" });
          // Give the worker a moment, then reload even if the event is missed.
          window.setTimeout(function () {
            window.location.reload();
          }, 1200);
        } else {
          window.location.reload();
        }
      })
      .catch(function () {
        window.location.reload();
      });
  }

  // ------------------------------------------------- favourites & offline

  function readFavorites() {
    try {
      var raw = localStorage.getItem(FAV_KEY);
      if (raw) favorites = JSON.parse(raw) || {};
    } catch (e) {
      // Unreadable or someone edited it by hand: start clean, stay usable.
      favorites = {};
    }
  }

  function writeFavorites() {
    try {
      localStorage.setItem(FAV_KEY, JSON.stringify(favorites));
    } catch (e) {
      /* storage may be unavailable; the app still works for this visit */
    }
  }

  function isFavorite(id) {
    return !!favorites[id];
  }

  function swPost(message) {
    try {
      if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage(message);
      }
    } catch (e) {
      // Without a worker the words still live on the page; only audio is lost.
    }
  }

  function paintFavButton(btn, id) {
    var saved = isFavorite(id);
    btn.setAttribute("aria-pressed", saved ? "true" : "false");
    btn.setAttribute("aria-label", saved ? "Saved for later" : "Save for later");
    btn.textContent = saved ? "\u2665" : "\u2661";
  }

  function favButton(item) {
    var btn = make("button", "fav-btn");
    btn.type = "button";
    paintFavButton(btn, item.id);
    btn.addEventListener("click", function () {
      toggleFavorite(item);
      paintFavButton(btn, item.id);
    });
    return btn;
  }

  function toggleFavorite(item) {
    var id = item.id;
    if (!id) return;
    if (favorites[id]) {
      delete favorites[id];
      writeFavorites();
      swPost({ type: "UNCACHE_FAVORITE", item: item });
    } else {
      favorites[id] = {
        id: id,
        sender: item.sender || "",
        text: item.text || "",
        audio: item.audio || null,
        saved_at: Date.now(),
      };
      writeFavorites();
      swPost({ type: "CACHE_FAVORITE", item: favorites[id] });
    }
    renderSaved();
  }

  function renderSaved() {
    var list = $("savedList");
    if (!list) return;
    list.textContent = "";

    var ids = Object.keys(favorites).sort(function (a, b) {
      return (favorites[b].saved_at || 0) - (favorites[a].saved_at || 0);
    });

    $("savedEmpty").hidden = ids.length > 0;
    ids.forEach(function (id) {
      list.appendChild(messageCard(favorites[id]));
    });
  }

  function showSaved(resting) {
    renderSaved();
    $("savedLead").textContent = resting
      ? "I'm resting right now, but here are some you saved."
      : "A few kind things you kept close.";
    setScreen("saved");
  }

  function setStatus(state) {
    var line = $("status");
    var text = $("statusText");
    if (!line || !text) return;
    line.classList.remove("is-offline", "is-checking");
    if (state === "offline") {
      line.classList.add("is-offline");
      text.textContent = "Showing what you saved";
    } else if (state === "checking") {
      line.classList.add("is-checking");
      text.textContent = "Checking\u2026";
    } else {
      text.textContent = "Here with you";
    }
  }

  // The network itself being unreachable shows as a TypeError; an HTTP error
  // from a running server does not, so a down Ollama stays a calm in-page note.
  function isOfflineError(err) {
    if (navigator.onLine === false) return true;
    return !!err && (err.name === "TypeError" || err.message === "Failed to fetch");
  }

  function probeServer() {
    if (!window.fetch) return Promise.resolve(false);
    var controller =
      typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = window.setTimeout(function () {
      if (controller) controller.abort();
    }, 4000);

    var options = controller ? { signal: controller.signal } : {};
    return fetch("/api/health", options)
      .then(function (res) {
        return res.ok;
      })
      .catch(function () {
        return false;
      })
      .then(function (ok) {
        window.clearTimeout(timer);
        return ok;
      });
  }

  function refreshStatus() {
    if (!navigator.onLine) {
      setStatus("offline");
      return Promise.resolve(false);
    }
    setStatus("checking");
    return probeServer().then(function (ok) {
      setStatus(ok ? "online" : "offline");
      return ok;
    });
  }

  function goResting() {
    setStatus("offline");
    showSaved(true);
  }

  // ---------------------------------------------------------------- crisis

  // Only used if the server ever omits resources. Public numbers, so safe as a
  // literal. The helper's private number is never hard-coded here.
  function fallbackResources() {
    return [
      { name: "Tele-MANAS", number: "14416", tel: "tel:14416" },
      { name: "Emergency", number: "112", tel: "tel:112" },
    ];
  }

  function showCrisis(data) {
    $("crisisMessage").textContent =
      data && data.message
        ? data.message
        : "You reached out, and that matters. Please reach someone who can be with you right now.";

    var box = $("crisisButtons");
    box.textContent = "";

    var resources =
      data && Array.isArray(data.resources) && data.resources.length
        ? data.resources
        : fallbackResources();

    resources.forEach(function (r) {
      var label = r.number ? r.name + " \u2014 " + r.number : r.name;
      var link = make("a", "crisis-call", label);
      link.href = r.tel || "tel:" + r.number;
      box.appendChild(link);
    });

    document.body.classList.add("crisis");
    ["home", "win", "challenge", "saved"].forEach(function (id) {
      $(id).hidden = true;
    });
    $("crisis").hidden = false;
    $("crisis").focus();
  }

  // ---------------------------------------------------------------- feeling

  function clearResult() {
    $("result").textContent = "";
  }

  function renderThinking() {
    clearResult();
    $("result").appendChild(make("p", "thinking", "Finding something kind\u2026"));
  }

  function setSending(isSending) {
    var btn = $("send");
    btn.disabled = isSending;
    btn.textContent = isSending ? "Finding something kind\u2026" : "Send";
  }

  function messageCard(item) {
    var card = make("div", "card");

    var head = make("div", "card-head");
    if (item.sender && item.sender !== "me") {
      head.appendChild(make("p", "sender", item.sender));
    } else {
      head.appendChild(make("span", "sender-spacer", ""));
    }
    if (item.id && item.id !== "me") {
      head.appendChild(favButton(item));
    }
    card.appendChild(head);

    if (item.text) {
      card.appendChild(make("p", "text", item.text));
    }
    if (item.audio) {
      var audio = make("audio", null);
      audio.controls = true;
      audio.preload = "none";
      audio.src = "/media/" + encodeURIComponent(item.audio);
      card.appendChild(audio);
    }
    return card;
  }

  function renderResult(data) {
    var result = $("result");
    result.textContent = "";

    if (data.lead) {
      result.appendChild(make("p", "lead", data.lead));
    }

    var messages = data.messages || [];
    var wins = data.wins || [];

    if (!messages.length && !wins.length) {
      result.appendChild(
        make(
          "p",
          "lead",
          "I couldn't find a note just now, but you're not alone in this."
        )
      );
    }

    messages.forEach(function (item) {
      result.appendChild(messageCard(item));
    });

    if (wins.length) {
      var card = make("div", "card remember");
      card.appendChild(make("p", "title", "Remember this?"));
      wins.forEach(function (w) {
        card.appendChild(make("p", "win", w.text));
      });
      result.appendChild(card);
    }

    $("againWrap").hidden = false;
  }

  function doFeel() {
    var text = ($("more").value || "").trim();
    var mood = selectedMood;

    if (!mood && !text) {
      clearResult();
      $("result").appendChild(
        make("p", "lead", "Take your time. Pick a feeling, or write a little first.")
      );
      return;
    }

    lastQuery = { mood: mood, text: text };
    setSending(true);
    renderThinking();

    post("/api/feel", {
      mood: mood,
      text: text,
      recently_shown_ids: Array.from(shown),
    })
      .then(function (data) {
        if (data.crisis) {
          showCrisis(data);
          return;
        }
        renderResult(data);
        var ids = (data.messages || []).map(function (m) {
          return m.id;
        });
        ids = ids.concat(
          (data.wins || []).map(function (w) {
            return w.id;
          })
        );
        markShown(ids);
      })
      .catch(function (err) {
        if (isOfflineError(err)) {
          setSending(false);
          goResting();
          return;
        }
        clearResult();
        $("result").appendChild(make("p", "lead", reachError()));
      })
      .then(function () {
        setSending(false);
      });
  }

  // ---------------------------------------------------------------- win

  function saveWin() {
    var text = ($("winText").value || "").trim();
    var status = $("winStatus");
    status.textContent = "";

    if (!text) {
      status.textContent = "Even a small one counts. Write something first.";
      return;
    }

    $("saveWin").disabled = true;
    post("/api/win", { text: text })
      .then(function (data) {
        if (data.crisis) {
          showCrisis(data);
          return;
        }
        $("winText").value = "";
        status.textContent = "Saved. That counts, and it's here for you.";
      })
      .catch(function () {
        status.textContent = reachError();
      })
      .then(function () {
        $("saveWin").disabled = false;
      });
  }

  // ---------------------------------------------------------------- challenge

  function requestStep(challenge) {
    var status = $("stepStatus");
    status.textContent = "Thinking of one small thing\u2026";

    post("/api/step", { challenge: challenge })
      .then(function (data) {
        if (data.crisis) {
          showCrisis(data);
          return;
        }
        lastChallenge = challenge;
        $("stepText").textContent = data.step || "";
        $("stepCard").hidden = false;
        status.textContent = "";
      })
      .catch(function () {
        status.textContent = reachError();
      });
  }

  function getStep() {
    $("stepCard").hidden = true;
    requestStep(($("challengeText").value || "").trim());
  }

  function shrinkStep() {
    $("stepCard").hidden = true;
    var base = lastChallenge || ($("challengeText").value || "").trim();
    requestStep("Make this even tinier and easier, one minute or less: " + base);
  }

  function doneStep() {
    $("stepCard").hidden = true;
    $("stepStatus").textContent = "One small thing done. That's enough for now.";
  }

  // ---------------------------------------------------------------- config

  function prettyMood(mood) {
    return String(mood).replace(/-/g, " ");
  }

  function renderMoods() {
    var box = $("moods");
    box.textContent = "";
    (config.moods || []).forEach(function (mood) {
      var btn = make("button", "mood", prettyMood(mood));
      btn.type = "button";
      btn.setAttribute("aria-pressed", "false");
      btn.addEventListener("click", function () {
        selectedMood = mood;
        Array.prototype.forEach.call(box.children, function (child) {
          child.setAttribute("aria-pressed", child === btn ? "true" : "false");
        });
      });
      box.appendChild(btn);
    });
  }

  function loadConfig() {
    return fetch("/api/config")
      .then(function (res) {
        if (!res.ok) throw new Error("config failed");
        return res.json();
      })
      .then(function (data) {
        config.friend_name = data.friend_name || "";
        config.moods = data.moods || [];
        $("greeting").textContent = config.friend_name
          ? "Hi, " + config.friend_name + "."
          : "Hi.";
        renderMoods();
      })
      .catch(function (err) {
        $("greeting").textContent = "Hi.";
        renderMoods();
        if (isOfflineError(err)) {
          goResting();
          return;
        }
        clearResult();
        $("result").appendChild(make("p", "lead", reachError()));
      });
  }

  // ---------------------------------------------------------------- boot

  function whenReady() {
    hideSplash();
    if (welcomeAlreadyShown()) {
      // Welcome already completed on this device: only the install nudge remains.
      maybePromptInstall();
    } else {
      openWelcome();
    }
    // A quiet check so the little dot tells the truth about being reachable.
    refreshStatus();
  }

  function welcomeAlreadyShown() {
    return readFlag(WELCOME_KEY);
  }

  function init() {
    loadShown();
    readFavorites();
    renderSaved();

    $("send").addEventListener("click", doFeel);
    $("again").addEventListener("click", function () {
      selectedMood = lastQuery.mood || selectedMood;
      $("more").value = lastQuery.text || "";
      doFeel();
    });
    $("openWin").addEventListener("click", function () {
      $("winStatus").textContent = "";
      setScreen("win");
    });
    $("openChallenge").addEventListener("click", function () {
      $("stepStatus").textContent = "";
      setScreen("challenge");
    });
    $("openSaved").addEventListener("click", function () {
      showSaved(false);
    });
    $("saveWin").addEventListener("click", saveWin);
    $("getStep").addEventListener("click", getStep);
    $("stepSmaller").addEventListener("click", shrinkStep);
    $("stepDone").addEventListener("click", doneStep);

    $("welcomeNext").addEventListener("click", welcomeNext);
    $("welcomeSkip").addEventListener("click", closeWelcome);
    $("a2hsAction").addEventListener("click", installNow);
    $("a2hsDismiss").addEventListener("click", dismissInstall);
    $("updateReload").addEventListener("click", reloadForUpdate);

    Array.prototype.forEach.call(
      document.querySelectorAll("[data-close]"),
      function (btn) {
        btn.addEventListener("click", function () {
          setScreen("home");
        });
      }
    );

    // The install prompt may arrive before or after we are ready.
    window.addEventListener("beforeinstallprompt", function (event) {
      event.preventDefault();
      deferredPrompt = event;
      if (welcomeAlreadyShown()) maybePromptInstall();
    });
    window.addEventListener("appinstalled", function () {
      writeFlag(A2HS_KEY);
      $("a2hs").hidden = true;
    });

    // Keep the little status dot honest, and let a returning connection be
    // noticed without the friend doing anything.
    window.addEventListener("offline", function () {
      setStatus("offline");
    });
    window.addEventListener("online", function () {
      refreshStatus();
    });

    // Never leave the splash up, even if loading hangs.
    window.setTimeout(hideSplash, 1800);

    loadConfig().then(whenReady, whenReady);
    registerServiceWorker();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
