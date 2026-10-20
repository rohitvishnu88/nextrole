export interface Me {
  email: string;
  name: string;
  picture: string;
  is_owner: boolean;
}

export type MeteredAction = "job_search" | "tailor" | "analyse" | "section_draft" | "resume_parse" | "search_brief";

export interface UsageAction {
  used: number;
  limit: number | null;
}

export interface UsageMe {
  month: string;
  resets_on: string;
  paused: boolean;
  actions: Record<MeteredAction, UsageAction>;
  owner?: {
    spent_usd: number;
    budget_usd: number;
    by_user: { email: string; spent_usd: number; counts: Record<string, number> }[];
    by_action: Record<string, number>;
  };
}

export interface Profile {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export type ApplicationStatus =
  | "saved"
  | "applied"
  | "interview"
  | "offer"
  | "rejected";

export interface Application {
  id: string;
  profile_id: string;
  job_title: string;
  company: string;
  location: string | null;
  url: string | null;
  status: ApplicationStatus;
  applied_date: string | null;
  notes: string | null;
  resume_file: string | null;
  cover_letter_file: string | null;
  created_at: string;
  updated_at: string;
  follow_up_date: string | null;
  match_score: number | null;
  analysis_id: string | null;
  overdue: boolean;
}

export interface TailorJob {
  job_id: string;
  status: "running" | "completed" | "failed";
  message: string;
  pdf_file?: string;
  cover_letter_file?: string;
  json_file?: string;
  url?: string;
}

export interface TailoredExperience {
  title: string;
  highlight: string;
  company: string;
  location: string;
  start_date: string;
  end_date: string;
  description: string[];
}

export interface TailoredResume {
  name: string;
  designation: string;
  work_right?: string;
  email: string;
  phone: string;
  website?: string;
  summary: string;
  experience: TailoredExperience[];
  [key: string]: unknown;
}

export type SignalConfidence = "high" | "medium" | "low";
export type SignalCategory =
  | "roles"
  | "skills"
  | "location"
  | "seniority"
  | "industries"
  | "exclusions";

export interface Signal {
  id: string;
  category: SignalCategory;
  label: string;
  confidence: SignalConfidence;
  source: string;
  active: boolean;
}

export interface SearchBrief {
  generated_at: string;
  headline: string;
  signals: Signal[];
}

export type JobSource = "linkedin" | "greenhouse" | "lever" | "yc";
export type JobStatus = "new" | "seen" | "applied" | "dismissed" | "closed";

export interface JobMatch {
  id: string;
  source: JobSource;
  title: string;
  company: string;
  location: string;
  url: string;
  relevance_score: number;
  match_reason: string;
  red_flags: string[];
  text_basis: "full" | "snippet";
  analysis_id?: string;
  status: JobStatus;
  first_seen_at: string;
  last_seen_at: string;
}

export interface JobSearchResult {
  status?: "searching";
  generated_at?: string;
  jobs?: JobMatch[];
  error?: string | null;
}

export interface TailorHistoryEntry {
  id: string;
  created_at: string;
  job_url: string;
  pdf_available: boolean;
  cover_letter_available: boolean;
  match_score: number | null;
  verdict: string | null;
}

export type FilterLikelihood = "high" | "medium" | "low" | "filler";
export type Meets = "yes" | "partly" | "no";
export type Verdict = "strong fit" | "genuine stretch" | "waste of time";

export interface Requirement {
  text: string;
  filter_likelihood: FilterLikelihood;
  why: string;
  key_terms: string[];
  meets: Meets;
  evidence: string;
  interview_answer: string;
}

export interface JobAnalysis {
  analysis_id: string;
  created_at: string;
  what_it_really_is: string;
  problem_being_solved: string;
  search_terms: string[];
  suspicious: string[];
  requirements: Requirement[];
  gaps_that_matter: string[];
  gaps_that_dont: string[];
  verdict: Verdict;
  verdict_reason: string;
  left_off: string[];
  match_score: number | null;
}

export interface ChangeEntry {
  location: string;
  kind: "reordered" | "reworded" | "expanded" | "shrunk" | "summary" | "skills";
  before: string;
  after: string;
  needs_confirmation: boolean;
  reason: string;
  stale?: boolean;
}

export interface FabricationFlag {
  location: string;
  kind: "number" | "skill" | "name" | "identity";
  text: string;
}

export interface AtsResult {
  contact: { email: boolean; phone: boolean };
  headings: { summary: boolean; experience: boolean; skills: boolean; education: boolean };
  terms: { term: string; present: boolean }[];
  text: string;
}

export interface TailorFit {
  analysis: JobAnalysis | null;
  changes: ChangeEntry[];
  fabrication_flags: FabricationFlag[];
  ats: AtsResult;
}

export type JobAnalysisStatus =
  | { status: "analysing" }
  | { status: "none" }
  | { status: "failed"; error: string }
  | { status: "ready"; analysis: JobAnalysis };

export interface ResumeVersionSummary {
  id: string;
  timestamp: string;
  change_summary: string;
}

export interface ResumeVersion extends ResumeVersionSummary {
  data: Record<string, unknown>;
}

export type SectionKind = "list_object" | "flat_list" | "grouped_list" | "scalar";

export interface SectionDraftRequest {
  action: "add" | "edit";
  item_index?: number;
  group?: string;
  skill?: string;
  instruction: string;
}

export interface SectionDraftResponse {
  items?: unknown[];
  item?: unknown;
}

export interface SectionApplyRequest {
  action: "add" | "edit" | "delete";
  item_index?: number;
  group?: string;
  skill?: string;
  item?: unknown;
}
