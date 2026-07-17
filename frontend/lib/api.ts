export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Job {
  id: number;
  company_id: number;
  company_name: string | null;
  job_source_id: number;
  external_job_id: string;
  canonical_url: string;
  title: string;
  description: string;
  location: string | null;
  remote_type: string | null;
  employment_type: string | null;
  department: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  posted_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  last_content_change_at: string;
  status: string;
}

export interface JobListResponse {
  items: Job[];
  limit: number;
  offset: number;
  total: number;
}

export interface CompanySummary {
  id: number;
  name: string;
  active_job_count: number;
}

export interface CompanyListResponse {
  items: CompanySummary[];
  total: number;
}

export interface JobSearchParams {
  q?: string;
  location?: string;
  company_id?: number;
  posted_since_days?: number;
  limit?: number;
  offset?: number;
}

function buildSearchQuery(params: JobSearchParams): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      usp.set(key, String(value));
    }
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

export async function searchJobs(params: JobSearchParams): Promise<JobListResponse> {
  const res = await fetch(`${API_URL}/jobs${buildSearchQuery(params)}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load jobs: ${res.status}`);
  return res.json();
}

export async function getJob(id: string | number): Promise<Job> {
  const res = await fetch(`${API_URL}/jobs/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load job ${id}: ${res.status}`);
  return res.json();
}

export async function listCompanies(): Promise<CompanyListResponse> {
  const res = await fetch(`${API_URL}/companies`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load companies: ${res.status}`);
  return res.json();
}
