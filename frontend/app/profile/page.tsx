"use client";

import { useEffect, useState } from "react";

import { getProfile, updateProfile } from "@/lib/api";

export default function ProfilePage() {
  const [resume, setResume] = useState("");
  const [initial, setInitial] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getProfile()
      .then((p) => {
        if (!alive) return;
        setResume(p.resume_text);
        setInitial(p.resume_text);
        setSavedAt(p.updated_at);
      })
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateProfile(resume);
      setInitial(updated.resume_text);
      setSavedAt(updated.updated_at);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const dirty = resume !== initial;
  const chars = resume.length;

  return (
    <div className="space-y-4 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">Your resume</h1>
        <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
          Paste your resume as plain text. It&apos;s used to score fit against each job posting.
          Only stored locally in your database. Save an empty resume to clear it.
        </p>
      </div>

      {loading ? (
        <p style={{ color: "var(--muted)" }}>Loading…</p>
      ) : (
        <>
          <textarea
            value={resume}
            onChange={(e) => setResume(e.target.value)}
            placeholder="Paste your resume text here..."
            rows={24}
            className="w-full rounded-lg border px-3 py-2 font-mono text-sm bg-transparent"
            style={{ borderColor: "var(--border)" }}
          />
          <div className="flex items-center justify-between text-sm" style={{ color: "var(--muted)" }}>
            <span>
              {chars.toLocaleString()} characters
              {savedAt && !dirty && (
                <span> · saved {new Date(savedAt).toLocaleString()}</span>
              )}
              {dirty && <span style={{ color: "var(--accent)" }}> · unsaved changes</span>}
            </span>
            <button
              onClick={save}
              disabled={saving || !dirty}
              className="rounded-lg px-4 py-2 text-white font-medium transition-opacity"
              style={{ background: "var(--accent)", opacity: saving || !dirty ? 0.5 : 1 }}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
          {error && (
            <p className="text-sm" style={{ color: "#dc2626" }}>
              {error}
            </p>
          )}
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            Changing your resume marks any previously computed fit/gap scores as stale — re-analyze
            individual rows on the Search page when you want fresh results.
          </p>
        </>
      )}
    </div>
  );
}
