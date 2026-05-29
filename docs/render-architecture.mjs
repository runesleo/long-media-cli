#!/usr/bin/env node
/** Render docs/architecture.svg → docs/architecture.png for GitHub README / social */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const svg = readFileSync(join(__dirname, 'architecture.svg'), 'utf8');
const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0d1117; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
  img, svg { display: block; width: 1280px; height: 720px; }
</style></head><body>${svg}</body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.setContent(html, { waitUntil: 'load' });
await page.screenshot({ path: join(__dirname, 'architecture.png'), type: 'png' });
await browser.close();
console.log('Wrote docs/architecture.png');
