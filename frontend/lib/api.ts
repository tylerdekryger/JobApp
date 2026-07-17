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
  description_clean: string;
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
  department?: string;
  remote_type?: string;
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

export interface FacetValue {
  value: string;
  count: number;
}

export interface FacetsResponse {
  departments: FacetValue[];
  locations: FacetValue[];
  companies: FacetValue[];
  remote_types: FacetValue[];
}

export async function getFacets(params: JobSearchParams): Promise<FacetsResponse> {
  const res = await fetch(`${API_URL}/jobs/facets${buildSearchQuery(params)}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load facets: ${res.status}`);
  return res.json();
}

export interface SourceSummary {
  id: number;
  company_id: number;
  company_name: string;
  provider: string;
  source_url: string;
  source_identifier: string;
  status: string;
  last_successful_sync: string | null;
  last_attempted_sync: string | null;
  last_error: string | null;
  active_job_count: number;
}

export interface SourceListResponse {
  items: SourceSummary[];
  total: number;
}

export interface SyncResult {
  source_id: number;
  jobs_found: number;
  jobs_added: number;
  jobs_updated: number;
  jobs_removed: number;
  duration_seconds: number;
}

export async function listSources(): Promise<SourceListResponse> {
  const res = await fetch(`${API_URL}/sources`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load sources: ${res.status}`);
  return res.json();
}

export async function createSource(url: string, companyName?: string): Promise<SourceSummary> {
  const res = await fetch(`${API_URL}/sources`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ url, company_name: companyName || undefined }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to create source: ${res.status}`);
  }
  return res.json();
}

export async function syncSource(sourceId: number): Promise<SyncResult> {
  const res = await fetch(`${API_URL}/sources/${sourceId}/sync`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to sync source: ${res.status}`);
  }
  return res.json();
}

export async function deleteSource(sourceId: number): Promise<void> {
  const res = await fetch(`${API_URL}/sources/${sourceId}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to delete source: ${res.status}`);
  }
}
