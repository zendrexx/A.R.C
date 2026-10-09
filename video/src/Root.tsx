import React from 'react';
import {Composition} from 'remotion';
import {ArcLogo} from './ArcLogo';

export const Root: React.FC = () => (
  <Composition
    id="ArcLogo"
    component={ArcLogo}
    durationInFrames={390}
    fps={60}
    width={1920}
    height={1080}
  />
);
