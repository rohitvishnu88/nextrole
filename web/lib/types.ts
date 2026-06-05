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
}

export interface TailorJob {
  job_id: string;
  status: "running" | "completed" | "failed";
  message: string;
  pdf_file?: string;
  cover_letter_file?: string;
  url?: string;
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
