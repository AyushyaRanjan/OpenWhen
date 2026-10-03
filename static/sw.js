/* Open When service worker. Caches the static shell so the app opens quickly,
   and only the favourites the friend explicitly saved. It never caches /api/
   responses and never stores a voice note the friend did not save. See
   AGENTS.md. */

var CACHE = "openwhen-shell-v6";
var FAV_CACHE = "openwhen-favourites-v1";
var RECENT_CACHE = "openwhen-recent-v1";
var FAV_PREFIX = "/__fav__/";

var SHELL = [
  "/",
  "/index.html",
  "/app.css",
  "/app.js",
  "/manifest.json",
  "/404.html",
  "/icon-192.png",
  "/icon-512.png",
  "/icon-192-maskable.png",
  "/icon-512-maskable.png",
];

self.addEventListener("install", function (event) {
  // Take over at once. A worker that waits for a tap may wait forever, and
  // being stuck on old files is worse than the rare refresh mid-read. The page
  // is reloaded by us on activate, so an online visit is always enough.
  event.waitUntil(
    Promise.all([
      caches.open(CACHE).then(function (cache) {
        return cache.addAll(SHELL);
      }),
      self.skipWaiting(),
    ])
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches
      .keys()
      .then(function (keys) {
        // A different shell cache already on disk means this is an update, not a
        // first install. Remember that so we can refresh the open pages below.
        // (Always bump CACHE's name when you change this file.)
        var wasUpdate = keys.some(function (key) {
          return key.indexOf("openwhen-shell-") === 0 && key !== CACHE;
        });

        return Promise.all(
          keys.map(function (key) {
            // Keep the shell, the friend's saved favourites, and the small set
            // of recent voice notes. Everything else is old and can go.
            if (key !== CACHE && key !== FAV_CACHE && key !== RECENT_CACHE) {
              return caches.delete(key);
            }
          })
        )
          .then(function () {
            return self.clients.claim();
          })
          .then(function () {
            // An open page is still running the previous files. Reload it once
            // so it picks up this version without the friend doing anything.
            if (!wasUpdate) return;
            return self.clients
              .matchAll({ type: "window" })
              .then(function (clients) {
                clients.forEach(function (client) {
                  client.navigate(client.url);
                });
              });
          });
      })
  );
});

self.addEventListener("message", function (event) {
  var data = event.data || {};

  if (data.type === "SKIP_WAITING") {
    self.skipWaiting();
    return;
  }

  if (data.type === "CACHE_FAVORITE" && data.item && data.item.id) {
    event.waitUntil(cacheFavorite(data.item));
    return;
  }

  if (data.type === "UNCACHE_FAVORITE" && data.item) {
    event.waitUntil(uncacheFavorite(data.item));
  }

  if (data.type === "SYNC_RECENT") {
    event.waitUntil(syncRecent(data.audio));
  }
});

function favoriteKey(id) {
  return FAV_PREFIX + id;
}

// Store the message itself (so its words survive even without the server) and,
// when there is one, its voice note. Both live in the favourites cache only.
function cacheFavorite(item) {
  return caches.open(FAV_CACHE).then(function (cache) {
    var payload = new Response(JSON.stringify(item), {
      headers: { "Content-Type": "application/json" },
    });
    var work = cache.put(new Request(favoriteKey(item.id)), payload);

    if (item.audio) {
      var audioUrl = "/media/" + encodeURIComponent(item.audio);
      // A missing or unplayable file must not abort the message being saved.
      work = work.then(function () {
        return cache.add(new Request(audioUrl)).catch(function () {});
      });
    }
    return work;
  });
}

function uncacheFavorite(item) {
  return caches.open(FAV_CACHE).then(function (cache) {
    var work = cache.delete(new Request(favoriteKey(item.id)));
    if (item.audio) {
      var audioUrl = "/media/" + encodeURIComponent(item.audio);
      work = work.then(function () {
        return cache.delete(new Request(audioUrl));
      });
    }
    return work;
  });
}

function recentAudioKey(name) {
  return "/media/" + encodeURIComponent(name);
}

// Keep exactly the voice notes for the recent messages, nothing more. The page
// sends the current list on every change; anything not on it is dropped, so
// this cache can never grow without bound.
function syncRecent(audioFiles) {
  var wanted = {};
  (audioFiles || []).forEach(function (name) {
    if (name) wanted[recentAudioKey(name)] = true;
  });

  return caches.open(RECENT_CACHE).then(function (cache) {
    return cache
      .keys()
      .then(function (requests) {
        return Promise.all(
          requests.map(function (req) {
            var path = new URL(req.url).pathname;
            if (!wanted[path]) return cache.delete(req);
          })
        );
      })
      .then(function () {
        return Promise.all(
          Object.keys(wanted).map(function (path) {
            return cache.match(path).then(function (hit) {
              // Already kept. A missing file is not an error here.
              return hit ? undefined : cache.add(path).catch(function () {});
            });
          })
        );
      });
  });
}

// A same-origin file we could not serve and never cached. Better than letting
// the browser throw its own network error at a calm moment.
function offlineResponse() {
  return new Response("", { status: 503, statusText: "Offline" });
}

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;

  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // What the friend typed or felt is never stored by the worker.
  if (url.pathname.indexOf("/api/") === 0) return;

  // Voice notes: serve a kept favourite or recent note from the cache,
  // otherwise let the network handle it. Never store a note that was not kept.
  if (url.pathname.indexOf("/media/") === 0) {
    event.respondWith(
      caches.open(FAV_CACHE).then(function (fav) {
        return fav.match(request).then(function (saved) {
          if (saved) return saved;
          return caches.open(RECENT_CACHE).then(function (rec) {
            return rec.match(request).then(function (kept) {
              return kept || fetch(request);
            });
          });
        });
      })
    );
    return;
  }

  // A page load: prefer fresh, but never leave the friend with nothing.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(function () {
        // Offline. Serve the exact page if we have it; otherwise the app shell
        // for the app itself, and the friendly 404 for anything else (so an
        // offline /admin.html never silently becomes the friend's screen).
        return caches.match(request).then(function (exact) {
          if (exact) return exact;
          if (url.pathname === "/" || url.pathname === "/index.html") {
            return caches.match("/index.html").then(function (shell) {
              return shell || caches.match("/");
            });
          }
          return caches.match("/404.html");
        });
      })
    );
    return;
  }

  // Static shell: serve from cache, refresh in the background.
  event.respondWith(
    caches.match(request).then(function (cached) {
      var network = fetch(request)
        .then(function (response) {
          if (response && response.ok) {
            var copy = response.clone();
            caches.open(CACHE).then(function (cache) {
              cache.put(request, copy);
            });
          }
          return response;
        })
        .catch(function () {
          // Return a real Response even when nothing was cached, or the browser
          // shows its own raw network error.
          return cached || offlineResponse();
        });
      return cached || network;
    })
  );
});
