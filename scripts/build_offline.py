"""Generate a content-versioned service worker from the final static Next export."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
out = root / 'apps/web/out'


def mirror_segment_prefetches():
    """Also emit each RSC segment payload at the dot-joined path the client actually requests.

    The export writes `<route>/__next.<segment>/__PAGE__.txt`, but the router asks for
    `<route>/__next.<segment>.__PAGE__.txt`. A plain static host cannot resolve one to the other, so every
    prefetch 404s and client-side navigation quietly degrades to a full page load. Copying the payload to the
    requested name costs a few kilobytes and keeps navigation instant on any static host.
    """
    copied = 0
    for payload in out.rglob('__next.*/__PAGE__.txt'):
        target = payload.parent.with_name(f'{payload.parent.name}.{payload.name}')
        if not target.exists() or target.read_bytes() != payload.read_bytes():
            target.write_bytes(payload.read_bytes())
        copied += 1
    return copied


mirrored = mirror_segment_prefetches()
files = sorted(p for p in out.rglob('*') if p.is_file() and p.name != 'sw.js' and p.suffix not in {'.map'})
revision = hashlib.sha256(b''.join(hashlib.sha256(p.read_bytes()).digest() for p in files)).hexdigest()[:16]
urls = ['/' + p.relative_to(out).as_posix() for p in files]
routes = ['/', '/investigate/', '/maintenance/', '/solar/', '/tech/', '/performance/', '/manager/', '/about/', '/assumptions/']
script = r'''/* Built by scripts/build_offline.py. Only same-origin public demo assets are cached. */
const CACHE = 'urjakavach-REVISION';
const PRECACHE = URLS;
self.addEventListener('install', event => {event.waitUntil((async()=>{const cache=await caches.open(CACHE);for(let i=0;i<PRECACHE.length;i+=12){await cache.addAll(PRECACHE.slice(i,i+12));}await self.skipWaiting();})());});
self.addEventListener('activate', event => {event.waitUntil((async()=>{for(const key of await caches.keys()){if(key.startsWith('urjakavach-')&&key!==CACHE)await caches.delete(key);}await self.clients.claim();})());});
self.addEventListener('fetch', event => {const request=event.request;const url=new URL(request.url);if(request.method!=='GET'||url.origin!==self.location.origin)return;
if(request.mode==='navigate'){event.respondWith((async()=>{try{return await fetch(request);}catch{const cache=await caches.open(CACHE);const clean=url.pathname.endsWith('/')?url.pathname:url.pathname+'/';return await cache.match(clean)||await cache.match(clean+'index.html')||await cache.match('/404.html')||Response.error();}})());return;}
event.respondWith((async()=>{const cache=await caches.open(CACHE);const cached=await cache.match(request);if(cached)return cached;const response=await fetch(request);if(response.ok&&(url.pathname.startsWith('/_next/')||url.pathname.startsWith('/demo/')))await cache.put(request,response.clone());return response;})());});
'''.replace('REVISION', revision).replace('URLS', json.dumps(sorted(set(urls + routes))))
(out / 'sw.js').write_text(script)
report = root / 'artifacts/metrics/offline-build.json'
report.parent.mkdir(parents=True, exist_ok=True)  # absent on a fresh clone and in a container build context
report.write_text(json.dumps({'cache_version': revision, 'precached_urls': len(set(urls + routes)), 'public_bytes': sum(p.stat().st_size for p in files)}, indent=2))
print(f'Offline cache built: {len(set(urls + routes))} URLs, revision {revision}, {mirrored} segment prefetches mirrored')

