"use client";

import { useCallback, useEffect, useState } from "react";

import {
  createDigestPreset,
  deleteDigestPreset,
  listDigestPresets,
  sendDigestNow,
  updateDigestPreset,
  type DigestPreset,
  type DigestSendResult,
} from "@/lib/api";

export default function DigestPage() {
  const [presets, setPresets] = useState<DigestPreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [titleContains, setTitleContains] = useState("");
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<DigestSendResult | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setPresets(await listDigestPresets());
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !titleContains.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await createDigestPreset({ name: name.trim(), title_contains: titleContains.trim() });
      setName("");
      setTitleContains("");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(p: DigestPreset) {
    try {
      await updateDigestPreset(p.id, { is_active: !p.is_active });
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  async function remove(p: DigestPreset) {
    if (!confirm(`Delete preset "${p.name}"?`)) return;
    try {
      await deleteDigestPreset(p.id);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  async function runNow() {
    setSending(true);
    setSendResult(null);
    setError(null);
    try {
      const r = await sendDigestNow();
      setSendResult(r);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold">Daily digest</h1>
        <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
          Save named boolean role-keyword queries. Each morning at 8am ET (Mon–Fri) you&apos;ll
          get one email covering jobs that appeared in the last 24 hours matching any active preset.
        </p>
      </div>

      <div className="card p-4 space-y-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h2 className="text-sm font-semibold">Send test email now</h2>
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
              Ignores the schedule. Requires SMTP_USER / SMTP_PASSWORD in your .env
              (Gmail app password recommended).
            </p>
          </div>
          <button
            type="button"
            onClick={runNow}
            disabled={sending}
            className="rounded-lg px-4 py-2 text-white font-medium text-sm disabled:opacity-50"
            style={{ background: "var(--accent)" }}
          >
            {sending ? "Sending…" : "Send test email"}
          </button>
        </div>
        {sendResult && (
          <div className="text-xs" style={{ color: "var(--muted)" }}>
            {sendResult.skipped ? (
              <p style={{ color: "#dc2626" }}>Skipped: {sendResult.skipped}</p>
            ) : (
              <p>
                Sent to <strong>{sendResult.to}</strong> · {sendResult.presets_run} preset
                {sendResult.presets_run === 1 ? "" : "s"} · {sendResult.total_matches} total match
                {sendResult.total_matches === 1 ? "" : "es"}. Subject: <code>{sendResult.subject}</code>
              </p>
            )}
          </div>
        )}
      </div>

      <form onSubmit={add} className="card p-4 space-y-3">
        <h2 className="text-sm font-semibold">Add a preset</h2>
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_2fr_auto] gap-3 items-end">
          <label className="flex flex-col text-sm">
            <span className="mb-1 font-medium" style={{ color: "var(--muted)" }}>Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Customer Success roles"
              className="rounded-lg border px-3 py-2 bg-transparent"
              style={{ borderColor: "var(--border)" }}
            />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1 font-medium" style={{ color: "var(--muted)" }}>Role keywords (boolean)</span>
            <input
              type="text"
              value={titleContains}
              onChange={(e) => setTitleContains(e.target.value)}
              placeholder="Customer Success AND (Manager OR Analyst OR GTM)"
              className="rounded-lg border px-3 py-2 bg-transparent"
              style={{ borderColor: "var(--border)" }}
            />
          </label>
          <button
            type="submit"
            disabled={saving || !name.trim() || !titleContains.trim()}
            className="rounded-lg px-4 py-2 text-white font-medium text-sm disabled:opacity-50"
            style={{ background: "var(--accent)" }}
          >
            {saving ? "Saving…" : "Add preset"}
          </button>
        </div>
      </form>

      {error && (
        <div className="card p-3 text-sm" style={{ color: "#dc2626" }}>{error}</div>
      )}

      {loading ? (
        <p className="text-sm" style={{ color: "var(--muted)" }}>Loading…</p>
      ) : presets.length === 0 ? (
        <div className="card p-6 text-sm text-center" style={{ color: "var(--muted)" }}>
          No presets yet. Add one above to start receiving the digest.
        </div>
      ) : (
        <div className="grid gap-3">
          {presets.map((p) => (
            <div key={p.id} className="card p-4 flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-base font-semibold">{p.name}</h3>
                  <span
                    className="text-xs rounded-full px-2 py-0.5"
                    style={{
                      background: p.is_active ? "#16a34a22" : "var(--bg)",
                      color: p.is_active ? "#16a34a" : "var(--muted)",
                      border: `1px solid ${p.is_active ? "#16a34a55" : "var(--border)"}`,
                    }}
                  >
                    {p.is_active ? "active" : "paused"}
                  </span>
                </div>
                <p className="text-xs mt-1 font-mono" style={{ color: "var(--muted)" }}>
                  {p.title_contains}
                </p>
                {p.last_sent_at && (
                  <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
                    Last sent: {new Date(p.last_sent_at).toLocaleString()}
                  </p>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => toggleActive(p)}
                  className="rounded-lg px-3 py-1.5 text-sm border"
                  style={{ borderColor: "var(--border)" }}
                >
                  {p.is_active ? "Pause" : "Resume"}
                </button>
                <button
                  onClick={() => remove(p)}
                  className="rounded-lg px-3 py-1.5 text-sm border"
                  style={{ borderColor: "#dc262655", color: "#dc2626" }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
