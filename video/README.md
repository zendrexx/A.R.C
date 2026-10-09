# A.R.C logo reveal

A 6.5-second Remotion animation using the existing extension icon and dashboard navy/mint palette. The icon traces on, its recall dot pulses once, and the vector A.R.C wordmark reveals as the icon moves into the final lockup. At 3 seconds, "Agent Recall and Continuity" begins to appear below the logo. The complete lockup holds from about 3.8 seconds to the end. There is no audio.

## Run

Requires Node.js 20+ and npm. From this directory:

```powershell
npm ci
npm start
```

## Export

```powershell
npm run check
npm run render
npm run poster
npm run gif
```

Exports go to `out/`: a 1920 × 1080, 60 fps H.264 MP4, a PNG of the finished logo, and an optional 960 × 540, 20 fps GIF. On Windows, `remotion.config.ts` reuses installed Chrome or Edge. Otherwise Remotion may download Chrome Headless Shell on the first render. Generated media and dependencies are ignored by Git.

Run `render` before `poster` or `gif`: those previews are extracted from the MP4 with Remotion's bundled FFmpeg, so they do not need another browser render. Persistent webpack caching is disabled to reduce temporary disk usage.

The composition and duration are in `src/Root.tsx`; colors, vector artwork, and timing are in `src/ArcLogo.tsx`. All animation is driven by frame numbers, so scrubbing and rendering produce the same result. The mark preserves the geometry of `../extension/media/arc.svg`; the A.R.C lettering is drawn as vectors. The tagline uses Segoe UI with Helvetica Neue, Arial, and sans-serif fallbacks, with no font downloads.

Remotion render reference: https://www.remotion.dev/docs/cli/render
