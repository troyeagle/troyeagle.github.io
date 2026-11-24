import { createHash } from 'node:crypto';
import { appendFileSync } from 'node:fs';
import { lstat, readdir, readFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';

const profiles = {
  clue: { repository: 'troyeagle/larp-clues-presentation', branch: 'main', manager: 'npm',
    lockfile: 'package-lock.json', output: 'build', publicUrl: '/clue', maps: false,
    install: 'npm ci --no-audit --no-fund', test: 'npm test -- --watchAll=false --runInBand', build: 'npm run build' },
  countdown: { repository: 'troyeagle/larp-countdown', branch: 'main', manager: 'yarn',
    lockfile: 'yarn.lock', output: 'build', publicUrl: '/countdown', maps: false,
    install: 'yarn install --frozen-lockfile --non-interactive', test: 'yarn test --watchAll=false --runInBand', build: 'yarn build' },
  'clue-viewer': { repository: 'troyeagle/clue-viewer', branch: 'master', manager: 'pnpm',
    lockfile: 'pnpm-lock.yaml', output: 'dist', publicUrl: '/clue-viewer', maps: false,
    install: 'pnpm install --frozen-lockfile', test: 'pnpm test', build: 'pnpm run build' },
  merger: { repository: 'troyeagle/image-merger-fe', branch: 'main', manager: 'npm',
    lockfile: 'package-lock.json', output: 'dist', publicUrl: '/merger', maps: false,
    install: 'npm ci --no-audit --no-fund', test: 'npm run test:unit -- --run', build: 'npm run build' },
  'ai-video-reverse': { repository: 'troyeagle/ai-video-reverse', branch: 'main', manager: 'python',
    lockfile: '', output: 'dist', publicUrl: '/ai-video-reverse', maps: false,
    install: 'true', test: 'python3 -m unittest discover -s tests -v', build: 'python3 scripts/build_static_pages.py' },
  'expedition-alfonso-showcase': { repository: 'troyeagle/expedition-alfonso-showcase', branch: 'main', manager: 'python',
    lockfile: '', output: 'dist', publicUrl: '/expedition-alfonso-showcase', maps: false,
    install: 'true', test: 'python3 -m unittest discover -s tests -v', build: 'python3 scripts/build_static_pages.py' },
};

const [command, app] = process.argv.slice(2);
const profile = Object.hasOwn(profiles, app) ? profiles[app] : null;
if (!profile || process.env.GITHUB_REPOSITORY !== profile.repository) {
  throw new Error('Caller repository does not match the static application allowlist');
}
if (command === 'profile') {
  if (!process.env.GITHUB_OUTPUT) throw new Error('GITHUB_OUTPUT is required');
  const values = { manager: profile.manager, lockfile: profile.lockfile, output: profile.output,
    public_url: profile.publicUrl, source_maps: String(profile.maps),
    release_ref: `refs/heads/${profile.branch}`, install: profile.install, test: profile.test, build: profile.build };
  appendFileSync(process.env.GITHUB_OUTPUT, Object.entries(values).map(([key, value]) => `${key}=${value}\n`).join(''));
  process.exit(0);
}
if (command !== 'package') throw new Error('Use profile or package');

const root = resolve(profile.output);
if (!(await lstat(root)).isDirectory()) throw new Error('Static output root must be a real directory');
const sha = process.env.GITHUB_SHA;
const runId = process.env.GITHUB_RUN_ID;
const runNumber = Number(process.env.GITHUB_RUN_NUMBER);
const runAttempt = Number(process.env.GITHUB_RUN_ATTEMPT || 1);
if (process.env.GITHUB_REF !== `refs/heads/${profile.branch}` ||
    !/^[a-f0-9]{40}$/.test(sha || '') || !/^[1-9][0-9]*$/.test(runId || '') ||
    !Number.isSafeInteger(runNumber) || runNumber < 1 ||
    !Number.isSafeInteger(runAttempt) || runAttempt < 1) {
  throw new Error('Missing or invalid trusted build identity');
}

const extensions = new Set(['html', 'js', 'css', 'json', 'png', 'jpg', 'jpeg', 'gif',
  'webp', 'ico', 'svg', 'txt', 'xml', 'woff', 'woff2', 'ttf', 'eot', 'map']);
const files = [];
let totalSize = 0;
async function walk(relative = '') {
  for (const name of (await readdir(join(root, relative))).sort()) {
    if (name.startsWith('.') || ['src', 'node_modules'].includes(name) || /[\x00-\x1f\\]/.test(name)) {
      throw new Error('Unexpected filename in static output');
    }
    const path = relative ? `${relative}/${name}` : name;
    const info = await lstat(join(root, path));
    if (path === '_site-sync.json') {
      if (!info.isFile()) throw new Error('Reserved manifest must be a regular file');
      continue;
    }
    if (info.isDirectory()) await walk(path);
    else if (info.isFile()) {
      const extension = name.split('.').at(-1).toLowerCase();
      if (!extensions.has(extension) || (!profile.maps && extension === 'map')) {
        throw new Error('Unsupported output or source map from a private application');
      }
      totalSize += info.size;
      if (totalSize > 256 * 1024 * 1024 || files.length >= 10000) throw new Error('Static output exceeds limits');
      const data = await readFile(join(root, path));
      files.push({ path, size: data.length, sha256: createHash('sha256').update(data).digest('hex') });
    } else throw new Error('Static output contains a symlink or special file');
  }
}
await walk();
if (!files.some(file => file.path === 'index.html')) throw new Error('Missing static index.html');
await writeFile(join(root, '_site-sync.json'), JSON.stringify({
  schema: 1, app, repository: profile.repository, sha, runId, runNumber, runAttempt, files,
}, null, 2) + '\n');
console.log(`Packaged ${files.length} files for /${app}/; source maps ${profile.maps ? 'allowed' : 'disabled'}`);
