/**
 * Narrative Intelligence Types
 */
export type NarrativeState = 'EARLY' | 'EXPANDING' | 'SATURATED' | 'FADING' | 'DORMANT';

export type NarrativeAssessment = {
  clusterId: string;
  origin: {
    eventId: string | null;
    authorId: string | null;
    authorName: string | null;
    trustScore: number;
  };
  velocity: number;
  echoScore: number;
  saturationScore: number;
  contradictionScore: number;
  lifecycle: NarrativeState;
  highQualityAmplifiers: string[];
  lowQualityAmplifiers: string[];
  socialStrength: number;
  socialConfidence: number;
};

export type SocialIntel = {
  originQuality: number;
  echoScore: number;
  saturationScore: number;
  lifecycle: NarrativeState;
  socialStrength: number;
  socialConfidence: number;
  probabilityDelta: number;
  confidenceDelta: number;
  alignmentDelta: number;
  narrativeDelta: number;
  whyHelpful: string[];
  whyRisky: string[];
  topOrigin: string | null;
  topAmplifiers: string[];
};
