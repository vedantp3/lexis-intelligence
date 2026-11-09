export type SourceChunk = {
  article: string;
  part: string;
  title: string;
  snippet: string;
};

export type GroundingValidation = {
  is_faithful: boolean;
  confidence_score: number;
  unsupported_claims: string[];
};

export type ConstitutionalAnswer = {
  summary: string;
  articles_cited: string[];
  detailed_legal_analysis: string;
  exceptions_or_limitations: string;
};

export type Message = {
  /** Client-side id (set for streamed replies so they can be updated in place). */
  id?: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
  audit?: GroundingValidation;
  answer?: ConstitutionalAnswer;
  fromCache?: boolean;
  latencyMs?: number;
  /** True while the answer is still streaming in. */
  streaming?: boolean;
};

export type ChatSession = {
  id: string;
  title: string;
  preview: string;
  timestamp: Date;
  messages: Message[];
};
