/* Open When service worker. Caches the static shell so the app opens quickly,
   and only the favourites the friend explicitly saved. It never caches /api/
   responses and never stores a voice note the friend did not save. See
   AGENTS.md. */

var CACHE = "openwhen-shell-v3";
var FAV_CACHE = "openwhen-favourites-v1";
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
  // No skipWaiting here on purpose: the page shows a "fresh version" prompt and
  // tells this worker when to take over, so an update never yanks the screen
  // out from under someone mid-sentence.
  event.waitUntil(
    caches
      .open(CACHE)
      .then(function (cache) {
        return cache.addAll(SHELL);
      })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches
      .keys()
      .then(function (keys) {
        return Promise.all(
          keys.map(function (key) {
            // Keep the shell and the friend's saved favourites. Everything else
            // is an old generation and can go.
            if (key !== CACHE && key !== FAV_CACHE) return caches.delete(key);
          })
        );
      })
      .then(function () {
        return self.clients.claim();
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

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;

  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // What the friend typed or felt is never stored by the worker.
  if (url.pathname.indexOf("/api/") === 0) return;

  // Voice notes: serve a saved favourite from the cache, otherwise let the
  // network handle it. Never store a note the friend did not save.
  if (url.pathname.indexOf("/media/") === 0) {
    event.respondWith(
      caches.open(FAV_CACHE).then(function (cache) {
        return cache.match(request).then(function (saved) {
          return saved || fetch(request);
        });
      })
    );
    return;
  }

  // A page load: prefer fresh, but never leave the friend with nothing.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(function () {
        return caches.match("/index.html");
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
          return cached;
        });
      return cached || network;
    })
  );
});
