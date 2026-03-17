const CACHE_NAME = 'visitor-portal-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/static/css/style.css',
    '/static/css/mobile-suite-v7.css',
    '/static/js/mobile-suite-v7.js',
    '/static/manifest.json',
    'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

self.addEventListener('fetch', event => {
    // We only try to cache GET requests that are static
    if (event.request.method === 'GET' && event.request.url.includes('/static/')) {
        event.respondWith(
            caches.match(event.request).then(response => {
                return response || fetch(event.request).then(fetchResponse => {
                    return caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, fetchResponse.clone());
                        return fetchResponse;
                    });
                });
            })
        );
    }
});
