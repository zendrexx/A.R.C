import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';

// Match the existing dashboard palette. The mark geometry comes from
// extension/media/arc.svg; the wordmark is vector artwork for consistent renders.
const colors = {
  navy: '#0b111b',
  mint: '#64dfb6',
  white: '#e6eef4',
  halo: '#163d3d',
};

const progress = (frame: number, start: number, end: number) =>
  interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.22, 1, 0.36, 1),
  });

const DrawPath: React.FC<{d: string; amount: number}> = ({d, amount}) => (
  <path
    d={d}
    pathLength={1}
    strokeDasharray={1}
    strokeDashoffset={1 - amount}
    opacity={amount > 0 ? 1 : 0}
  />
);

export const ArcLogo: React.FC = () => {
  const frame = useCurrentFrame();
  const form = progress(frame, 8, 59);
  const expand = progress(frame, 62, 112);
  const reveal = progress(frame, 76, 133);
  const settle = progress(frame, 118, 160);
  const dot = progress(frame, 44, 65);
  const tagline = progress(frame, 180, 230);
  const halo = interpolate(frame, [0, 45, 100, 175], [0, 0.6, 0.3, 0.18], {
    extrapolateRight: 'clamp',
  });
  const iconCenter = 960 - expand * 398;
  const iconSize = 254 - expand * 30;
  const wordmarkX = 742;
  const scale = 1.75;

  return (
    <AbsoluteFill style={{backgroundColor: colors.navy}}>
      <AbsoluteFill style={{
        opacity: halo,
        background: `radial-gradient(ellipse 620px 430px at ${iconCenter}px 540px, ${colors.halo}, transparent)`,
      }} />
      <svg width="1920" height="1080" viewBox="0 0 1920 1080"
        role="img" aria-label="A.R.C — Agent Recall and Continuity">
        <defs>
          <clipPath id="wordmark-reveal">
            <rect x={wordmarkX - 16} y="384" width={910 * reveal} height="300" />
          </clipPath>
          <linearGradient id="reveal-light" x1="0" x2="1">
            <stop offset="0" stopColor={colors.white} />
            <stop offset="0.5" stopColor="#ffffff" />
            <stop offset="1" stopColor={colors.white} />
          </linearGradient>
        </defs>

        <g transform={`translate(0 ${-40 * tagline})`}>
        <g transform={`translate(${iconCenter - iconSize / 2} ${540 - iconSize / 2}) scale(${iconSize / 24})`}>
          <g fill="none" stroke={colors.mint} strokeWidth="1.7"
            strokeLinecap="round" strokeLinejoin="round">
            <DrawPath d="M5 18V9a7 7 0 0 1 14 0v9" amount={form} />
            <DrawPath d="M5 12h14" amount={progress(frame, 28, 58)} />
            <DrawPath d="M9 18v-3" amount={progress(frame, 38, 62)} />
            <DrawPath d="M15 18v-3" amount={progress(frame, 41, 65)} />
          </g>
          <circle cx="12" cy="21" r={dot} fill={colors.mint} />
          <circle cx="12" cy="21" r={1 + progress(frame, 54, 93) * 3}
            fill="none" stroke={colors.mint} strokeWidth="0.15"
            opacity={interpolate(frame, [54, 62, 93], [0, 0.55, 0], {
              extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
            })} />
        </g>

        <g clipPath="url(#wordmark-reveal)">
          <g transform={`translate(${wordmarkX + (1 - settle) * 10} 428) scale(${scale})`}
            fill="none" stroke="url(#reveal-light)" strokeWidth="12"
            strokeLinecap="square" strokeLinejoin="round">
            <path d="M0 128L46 0L92 128M16 86H76" />
            <path d="M157 128V0H201C230 0 244 13 244 35S230 71 201 71H157M202 71L249 128" />
            <path d="M410 17C398 5 385 0 369 0C330 0 310 26 310 64S330 128 369 128C385 128 398 123 410 111" />
          </g>
          <g fill={colors.mint} transform={`translate(${wordmarkX} 428) scale(${scale})`}>
            <circle cx="124" cy="126" r="7" />
            <circle cx="280" cy="126" r="7" />
          </g>
        </g>
        </g>
        <text
          x="960"
          y={715 + (1 - tagline) * 12}
          textAnchor="middle"
          fill={colors.white}
          opacity={tagline * 0.88}
          fontFamily={'"Segoe UI", "Helvetica Neue", Arial, sans-serif'}
          fontSize="38"
          fontWeight="400"
          letterSpacing="1.2"
        >
          Agent Recall and Continuity
        </text>
      </svg>
    </AbsoluteFill>
  );
};
