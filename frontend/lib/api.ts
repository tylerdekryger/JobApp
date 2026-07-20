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
  reopened_at: string | null;
  status: string;
  fit_summary: string | null;
  gap_summary: string | null;
  analyzed_at: string | null;
  analysis_is_stale: boolean;
  market_check_summary: string | null;
  market_check_url: string | null;
  market_check_at: string | null;
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
  title_contains?: string;
  company_id?: number;
  posted_since_days?: number;
  sort?: string; // added_desc | added_asc | posted_desc | posted_asc
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

export interface Profile {
  resume_text: string;
  resume_hash: string;
  updated_at: string | null;
}

export async function getProfile(): Promise<Profile> {
  const res = await fetch(`${API_URL}/profile`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load profile: ${res.status}`);
  return res.json();
}

export async function updateProfile(resumeText: string): Promise<Profile> {
  const res = await fetch(`${API_URL}/profile`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ resume_text: resumeText }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to save profile: ${res.status}`);
  }
  return res.json();
}

export interface AnalyzeJobResponse {
  job_id: number;
  fit_summary: string;
  gap_summary: string;
  analyzed_at: string;
}

export async function analyzeJob(jobId: number): Promise<AnalyzeJobResponse> {
  const res = await fetch(`${API_URL}/jobs/${jobId}/analyze`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to analyze job: ${res.status}`);
  }
  return res.json();
}

export interface MarketCheckResponse {
  job_id: number;
  summary: string;
  linkedin_url: string | null;
  checked_at: string;
}

export async function marketCheckJob(jobId: number): Promise<MarketCheckResponse> {
  const res = await fetch(`${API_URL}/jobs/${jobId}/market-check`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to market-check job: ${res.status}`);
  }
  return res.json();
}

export interface DigestPreset {
  id: number;
  name: string;
  title_contains: string;
  is_active: boolean;
  last_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DigestSendResult {
  presets_run: number;
  total_matches: number;
  to: string;
  subject: string;
  skipped: string | null;
}

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function listDigestPresets(): Promise<DigestPreset[]> {
  return unwrap(await fetch(`${API_URL}/digests`, { cache: "no-store" }));
}

export async function createDigestPreset(
  input: { name: string; title_contains: string; is_active?: boolean },
): Promise<DigestPreset> {
  return unwrap(
    await fetch(`${API_URL}/digests`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function updateDigestPreset(
  id: number,
  patch: Partial<{ name: string; title_contains: string; is_active: boolean }>,
): Promise<DigestPreset> {
  return unwrap(
    await fetch(`${API_URL}/digests/${id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(patch),
    }),
  );
}

export async function deleteDigestPreset(id: number): Promise<void> {
  await unwrap<void>(await fetch(`${API_URL}/digests/${id}`, { method: "DELETE" }));
}

export async function sendDigestNow(): Promise<DigestSendResult> {
  return unwrap(await fetch(`${API_URL}/digests/run-now`, { method: "POST" }));
}

export interface DiscoverCandidate {
  token: string;
  company_name: string;
  source_url: string;
  job_count: number;
  already_registered: boolean;
}

export interface DiscoverResponse {
  candidates: DiscoverCandidate[];
  total_tokens_seen: number;
  filtered_out: number;
}

export async function extractCandidates(text: string): Promise<DiscoverResponse> {
  const res = await fetch(`${API_URL}/discover/extract`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to extract: ${res.status}`);
  }
  return res.json();
}

export interface RunAutoDiscoverResponse {
  query: string;
  tokens_found: number;
  new_boards_added: number;
  jobs_added: number;
  added_tokens: string[];
  skipped_too_large: string[];
  skipped: string | null;
}

export async function runAutoDiscoverNow(): Promise<RunAutoDiscoverResponse> {
  const res = await fetch(`${API_URL}/discover/run-now`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to run auto-discover: ${res.status}`);
  }
  return res.json();
}

export async function searchCandidates(query: string): Promise<DiscoverResponse> {
  const res = await fetch(`${API_URL}/discover/search`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Failed to search: ${res.status}`);
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
