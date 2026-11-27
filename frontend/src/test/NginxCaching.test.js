import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// Caching policy of frontend/nginx.conf (the Docker image's web server).
//
// After a redeploy, a cached index.html names chunks that no longer exist, and the page cannot recover even by
// reloading. Every HTML response must therefore be uncacheable, while content-hashed files under /assets/ keep
// their long-lived caching. No nginx binary is available to the tests, so this file models nginx's documented
// request handling for the directives that nginx.conf uses: location selection (exact "=", then the longest
// prefix, then regular expressions in order), the index directive and the try_files fallback as internal
// redirects that select a location again, and add_header/expires of the location that finally serves the file.
// It checks the configuration's structure; it does not replace running nginx (`nginx -t`).

const conf = readFileSync(resolve(__dirname, '../../nginx.conf'), 'utf-8').replace(/\r\n/g, '\n');

/** The server block's own directives and its location blocks (nginx.conf has no nested locations). */
function parse(text) {
  const body = text.replace(/#.*$/gm, '');
  const locations = [];
  const locationRe = /location\s+(=|~\*|~|\^~)?\s*(\S+)\s*\{([^{}]*)\}/g;
  let match;
  while ((match = locationRe.exec(body))) {
    locations.push({ modifier: match[1] || '', path: match[2], directives: directives(match[3]) });
  }
  const serverLevel = directives(body.replace(locationRe, '').replace(/^\s*server\s*\{/, ''));
  return { locations, serverLevel };
}

function directives(block) {
  return block
    .split(';')
    .map((d) => d.trim())
    .filter(Boolean)
    .map((d) => {
      const [name, ...args] = d.match(/"[^"]*"|\S+/g);
      return { name, args: args.map((a) => a.replace(/^"|"$/g, '')) };
    });
}

const { locations, serverLevel } = parse(conf);

function selectLocation(uri) {
  const exact = locations.find((l) => l.modifier === '=' && l.path === uri);
  if (exact) return exact;
  const prefixes = locations
    .filter((l) => (l.modifier === '' || l.modifier === '^~') && uri.startsWith(l.path))
    .sort((a, b) => b.path.length - a.path.length);
  if (prefixes[0]?.modifier === '^~') return prefixes[0];
  const regex = locations.find(
    (l) =>
      l.modifier.startsWith('~') && new RegExp(l.path, l.modifier === '~*' ? 'i' : '').test(uri)
  );
  return regex || prefixes[0];
}

const has = (location, name) => location.directives.some((d) => d.name === name);
const args = (location, name) =>
  location.directives.filter((d) => d.name === name).map((d) => d.args);

/** How nginx answers a GET of `uri`, given the files of the built site. */
function request(uri, files, redirects = 0) {
  expect(redirects).toBeLessThan(10); // nginx stops internal redirect loops too
  const location = selectLocation(uri);
  if (has(location, 'proxy_pass')) return { status: 'proxied', location };
  if (uri.endsWith('/')) {
    const index = (args(location, 'index')[0] ||
      args({ directives: serverLevel }, 'index')[0] ||
      [])[0];
    if (index && files.has(uri + index)) return request(uri + index, files, redirects + 1);
  }
  const tryFiles = args(location, 'try_files')[0];
  if (tryFiles) {
    for (const candidate of tryFiles.slice(0, -1)) {
      const path = candidate.replace('$uri', uri);
      if (!path.endsWith('/') && files.has(path)) return serve(path, location);
    }
    return request(tryFiles[tryFiles.length - 1], files, redirects + 1); // the fallback URI: internal redirect
  }
  return files.has(uri) ? serve(uri, location) : { status: 404, location };
}

function serve(path, location) {
  // add_header of a location replaces those of the server level (nginx inheritance), it does not add to them.
  const own = args(location, 'add_header');
  const headers = Object.fromEntries(
    (own.length ? own : args({ directives: serverLevel }, 'add_header')).map(([k, v]) => [k, v])
  );
  const expires = args(location, 'expires')[0]?.[0];
  return { status: 200, path, headers, expires, location };
}

const SITE = new Set([
  '/index.html',
  '/assets/index-Ab12Cd34.js',
  '/assets/index-Ef56Gh78.css',
  '/favicon.svg',
]);
const NO_CACHE = 'no-cache, no-store, must-revalidate';

describe('caching of the HTML entry point (nginx.conf)', () => {
  it.each(['/', '/index.html'])('%s is served uncacheable', (uri) => {
    const response = request(uri, SITE);
    expect(response).toMatchObject({ status: 200, path: '/index.html' });
    expect(response.headers['Cache-Control']).toBe(NO_CACHE);
    expect(response.headers.Pragma).toBe('no-cache');
    expect(response.headers.Expires).toBe('0');
    expect(response.expires).toBeUndefined();
  });

  it.each(['/explorer', '/planet/K2-18%20b', '/compare', '/no/such/page'])(
    'the SPA fallback for %s is index.html, uncacheable',
    (uri) => {
      const response = request(uri, SITE);
      expect(response).toMatchObject({ status: 200, path: '/index.html' });
      expect(response.headers['Cache-Control']).toBe(NO_CACHE);
    }
  );

  it('sends the headers with every status code ("always")', () => {
    const html = selectLocation('/index.html');
    const headers = args(html, 'add_header');
    expect(headers.map((a) => a[0]).sort()).toEqual(['Cache-Control', 'Expires', 'Pragma']);
    expect(headers.every((a) => a[a.length - 1] === 'always')).toBe(true);
  });

  it('keeps long-lived caching for content-hashed assets', () => {
    for (const uri of ['/assets/index-Ab12Cd34.js', '/assets/index-Ef56Gh78.css']) {
      const response = request(uri, SITE);
      expect(response).toMatchObject({ status: 200, path: uri, expires: '1y' });
      expect(response.headers['Cache-Control']).toBe('public, immutable');
    }
  });

  it('answers 404 for a missing asset instead of HTML (a stale chunk fails as a chunk)', () => {
    expect(request('/assets/index-Deleted0.js', SITE).status).toBe(404);
  });

  it('leaves other files and the proxied paths as they were', () => {
    expect(request('/favicon.svg', SITE)).toMatchObject({
      status: 200,
      headers: {},
      expires: undefined,
    });
    expect(request('/api/v1/planets', SITE).status).toBe('proxied');
    expect(request('/health', SITE).status).toBe('proxied');
    expect(request('/ready', SITE).status).toBe('proxied');
  });

  it('has no server-level add_header that the locations would silently drop', () => {
    expect(args({ directives: serverLevel }, 'add_header')).toEqual([]);
  });
});
