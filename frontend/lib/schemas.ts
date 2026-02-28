import { z } from "zod";

export const AnalyzeRequestSchema = z.object({
  csv: z.string().min(1),
  unit_col: z.string().min(1),
  time_col: z.string().min(1),
  y_col: z.string().min(1),
  treated_col: z.string().min(1),
  policy_start: z.string().min(1)
});

export const DidSchema = z.object({
  ate: z.number(),
  ci_low: z.number(),
  ci_high: z.number(),
  p_value: z.number()
});

export const CountsSchema = z.object({
  n_obs: z.number(),
  n_units: z.number(),
  n_units_treated: z.number(),
  n_units_control: z.number()
});

export const GroupMeanPointSchema = z.object({
  t: z.string(),
  treated_mean: z.number(),
  control_mean: z.number()
});

export const PredVsActualPointSchema = z.object({
  t: z.string(),
  y_actual: z.number(),
  y_pred: z.number()
});

export const EffectPointSchema = z.object({
  t: z.string(),
  effect: z.number(),
  cum_effect: z.number()
});

export const DiagnosticsSchema = z.object({
  pretrend_flag: z.enum(["ok", "warn"]),
  messages: z.array(z.string()),
  missing_rates: z.record(z.number()).default({}),
  outlier_count: z.number().default(0),
  pre_periods: z.number().default(0),
  post_periods: z.number().default(0)
});

export const AnalyzeResponseSchema = z.object({
  did: DidSchema,
  counts: CountsSchema,
  series: z.object({
    group_means: z.array(GroupMeanPointSchema),
    pred_vs_actual: z.array(PredVsActualPointSchema),
    effect_series: z.array(EffectPointSchema)
  }),
  diagnostics: DiagnosticsSchema,
  report_token: z.string().optional()
});

export const ErrorResponseSchema = z.object({
  message: z.string(),
  details: z.array(z.string()).default([])
});

export const SummaryConfigSchema = z.object({
  unit_col: z.string().min(1),
  time_col: z.string().min(1),
  y_col: z.string().min(1),
  treated_col: z.string().min(1),
  policy_start: z.string().min(1)
});

export const SummarizeRequestSchema = z.object({
  config: SummaryConfigSchema,
  analysis: AnalyzeResponseSchema
});

export const SummarizeResponseSchema = z.object({
  headline: z.string(),
  summary: z.string(),
  warnings: z.array(z.string()).default([]),
  next_steps: z.array(z.string()).default([])
});

export const SummarizeStatusSchema = z.object({
  enabled: z.boolean(),
  message: z.string()
});

export type AnalyzeRequestInput = z.infer<typeof AnalyzeRequestSchema>;
export type AnalyzeResponse = z.infer<typeof AnalyzeResponseSchema>;
export type SummarizeResponse = z.infer<typeof SummarizeResponseSchema>;
export type SummarizeStatus = z.infer<typeof SummarizeStatusSchema>;
