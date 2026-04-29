import { z } from "zod";

export const toxicityFeatureSchema = z.object({
  name: z.string(),
  contribution: z.number()
});

export const toxicityExplanationSchema = z.object({
  calibratedProbability: z.number(),
  adjustedProbability: z.number(),
  threshold: z.number(),
  features: z.array(toxicityFeatureSchema)
});

export const toxicityAnalysisResultSchema = z.object({
  analysisId: z.string(),
  label: z.union([z.literal(0), z.literal(1)]),
  toxicProbability: z.number(),
  model: z.object({
    modelKey: z.string(),
    modelVersion: z.string()
  }),
  reportLevel: z.literal("full"),
  explanation: toxicityExplanationSchema,
  createdAt: z.string()
});

export type ToxicityFeature = z.infer<typeof toxicityFeatureSchema>;
export type ToxicityExplanation = z.infer<typeof toxicityExplanationSchema>;
export type ToxicityAnalysisResult = z.infer<typeof toxicityAnalysisResultSchema>;

export interface ProblemDetailsError {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  errors?: Array<{
    field?: string;
    message?: string;
  }>;
}
