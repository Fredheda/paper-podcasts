// @vitest-environment node
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { networkInterfaces } from 'node:os';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import config from './playwright.config';

const SERVER = fileURLToPath(new URL('./server.js', import.meta.url));
const DOCKERFILE = fileURLToPath(new URL('./Dockerfile', import.meta.url));
const hasIpv6Loopback = Object.values(networkInterfaces()).some((addresses) =>
  addresses?.some((entry) => entry.address === '::1')
);

// Starts server.js on a free port and returns the address it logs. Only ever
// called with loopback hosts: a test must not expose the machine.
function boundAddress(host?: string): Promise<string> {
  const env: NodeJS.ProcessEnv = { ...process.env, PORT: '0' };
  delete env.HOST;
  if (host) env.HOST = host;
  const child = spawn(process.execPath, [SERVER], {
    env,
    stdio: ['ignore', 'pipe', 'inherit']
  });
  return new Promise<string>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('server.js did not start')), 10_000);
    child.once('error', reject);
    child.stdout.on('data', (chunk: Buffer) => {
      const match = /Server is running on (\S+):\d+/.exec(chunk.toString());
      if (match) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    });
  }).finally(() => {
    child.kill();
  });
}

describe('frontend server host', () => {
  it('server.js defaults to loopback', async () => {
    expect(await boundAddress()).toBe('127.0.0.1');
  });

  it.skipIf(!hasIpv6Loopback)('server.js binds the host it is given', async () => {
    expect(await boundAddress('::1')).toBe('::1');
  });

  it('the container image sets HOST to 0.0.0.0', () => {
    const stages = readFileSync(DOCKERFILE, 'utf8').split(/^FROM /m);
    expect(stages[stages.length - 1]).toMatch(/^ENV HOST=0\.0\.0\.0$/m);
  });

  it('the Playwright web server sets HOST to 127.0.0.1', () => {
    const servers = [config.webServer ?? []].flat();
    const web = servers.find((server) => server.command.includes('server.js'));
    expect(web?.env?.HOST).toBe('127.0.0.1');
  });
});
