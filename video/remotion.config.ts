import {existsSync} from 'node:fs';
import {Config} from '@remotion/cli/config';

// This small composition does not need a persistent webpack disk cache.
Config.setCachingEnabled(false);

// Reuse an installed browser on Windows, avoiding an extra browser download.
if (process.platform === 'win32') {
  const browser = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  ].find((path) => existsSync(path));
  if (browser) Config.setBrowserExecutable(browser);
}
