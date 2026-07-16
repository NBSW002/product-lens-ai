/*
import { FormEvent, useEffect, useRef, useState } from "react";

import { createJob, getHealth, getJob, retryJob } from "./api";
import { AnalysisTrace } from "./components/AnalysisTrace";
import { InsightGrid } from "./components/InsightGrid";
import { ProductSummary } from "./components/ProductSummary";
import { ProgressTimeline } from "./components/ProgressTimeline";
import { QualityPanel } from "./components/QualityPanel";
import { ScriptPanel } from "./components/ScriptPanel";
import type { Job } from "./types";

const demoUrl = "https://www.amazon.com/dp/B0CXT9RSGQ";

export default function App() {
  const [url, setUrl] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"demo" | "live" | "unavailable">("unavailable");
  const pollRef = useRef<number | null>(null);

  async function poll(id: string) {
    try {
      const current = await getJob(id);
      setJob(current);
      if (current.status === "queued" || current.status === "running") {
        pollRef.current = window.setTimeout(() => void poll(id), 700);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "获取任务状态失败");
    }
  }

  useEffect(() => {
    void getHealth()
      .then((health) => setMode(health.mode === "live" ? "live" : "demo"))
      .catch(() => setMode("unavailable"));
    return () => { if (pollRef.current) window.clearTimeout(pollRef.current); };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!url.trim()) return;
    setError("");
    setJob(null);
    try {
      const created = await createJob(url.trim());
      setJob(created);
      await poll(created.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建分析任务失败");
    }
  }

  async function retry() {
    if (!job) return;
    setError("");
    const queued = await retryJob(job.id);
    setJob(queued);
    await poll(queued.id);
  }

  const busy = job?.status === "queued" || job?.status === "running";
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top"><span>PA</span><strong>Product<span>Lens</span></strong></a>
        <div className={`mode-badge ${mode}`}><i />{mode === "live" ? "真实 API" : mode === "demo" ? "演示模式" : "服务未连接"}</div>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-glow" />
          <span className="hero-tag">AI · 产品理解 · 内容生成</span>
          <h1>把商品链接，变成<br /><em>有证据的内容洞察</em></h1>
          <p>融合 Amazon 商品数据、通义千问视觉理解与 DeepSeek 分析，生成产品洞察和可直接使用的短视频口播。</p>
          <form className="url-form" onSubmit={submit}>
            <label htmlFor="amazon-url">Amazon 商品链接</label>
            <div className="url-input-wrap">
              <span>↗</span>
              <input id="amazon-url" type="url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="粘贴 Amazon 商品链接，例如 https://amazon.com/dp/..." required />
              <button type="submit" disabled={busy}>{busy ? "分析中…" : "开始分析"}<b aria-hidden="true">→</b></button>
            </div>
            <button className="demo-link" type="button" onClick={() => setUrl(demoUrl)}>使用示例商品</button>
          </form>
          {error && <div className="error-banner" role="alert"><strong>分析未开始</strong><span>{error}</span></div>}
        </section>

        {job && !job.result && job.status !== "failed" && <ProgressTimeline stage={job.stage} progress={job.progress} />}
        {job && job.trace_events.length > 0 && <AnalysisTrace events={job.trace_events} />}
        {job?.status === "failed" && <div className="error-banner result-error" role="alert"><strong>分析失败</strong><span>{job.error}</span><button onClick={retry}>重新尝试</button></div>}

        {job?.result && (
          <div className="results">
            <ProductSummary facts={job.result.facts} />
            <InsightGrid analysis={job.result.analysis} />
            <div className="final-grid">
              <ScriptPanel script={job.result.analysis.voiceover} />
              <QualityPanel report={job.result.quality} />
            </div>
          </div>
        )}
      </main>
      <footer><span>ProductLens · AI Product Intelligence</span><span>事实优先 · 来源可追溯 · 内容有边界</span></footer>
    </div>
  );
}
*/

import { FormEvent, useEffect, useRef, useState } from "react";

import {
  createJob,
  getHealth,
  getJob,
  getMe,
  getPoints,
  getStoredToken,
  login,
  logout,
  register,
  retryJob,
} from "./api";
import { AnalysisTrace } from "./components/AnalysisTrace";
import { InsightGrid } from "./components/InsightGrid";
import { ProductSummary } from "./components/ProductSummary";
import { ProgressTimeline } from "./components/ProgressTimeline";
import { QualityPanel } from "./components/QualityPanel";
import { ScriptPanel } from "./components/ScriptPanel";
import type { Job, User } from "./types";

const demoUrl = "https://www.amazon.com/dp/B0CXT9RSGQ";
type AuthMode = "login" | "register";

export default function App() {
  const [url, setUrl] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"demo" | "live" | "unavailable">("unavailable");
  const pollRef = useRef<number | null>(null);

  async function refreshUser() {
    const current = await getMe();
    setUser(current);
  }

  async function refreshPoints() {
    const points = await getPoints();
    setUser((current) => current ? { ...current, points_balance: points.balance } : current);
  }

  async function poll(id: string) {
    try {
      const current = await getJob(id);
      setJob(current);
      if (current.status === "queued" || current.status === "running") {
        pollRef.current = window.setTimeout(() => void poll(id), 700);
      } else {
        await refreshPoints();
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to load job status");
    }
  }

  useEffect(() => {
    void getHealth()
      .then((health) => setMode(health.mode === "live" ? "live" : "demo"))
      .catch(() => setMode("unavailable"));
    if (getStoredToken()) {
      void refreshUser().catch(() => setUser(null));
    }
    return () => {
      if (pollRef.current) window.clearTimeout(pollRef.current);
    };
  }, []);

  async function submitAuth(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const response = authMode === "register"
        ? await register({ email, username: username || undefined, password })
        : await login({ email, password });
      setUser(response.user);
      setPassword("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication failed");
    }
  }

  async function signOut() {
    await logout();
    setUser(null);
    setJob(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!url.trim() || !user) return;
    if (user.points_balance < 1) {
      setError("Insufficient points");
      return;
    }
    setError("");
    setJob(null);
    try {
      const created = await createJob(url.trim());
      setJob(created);
      await refreshPoints();
      await poll(created.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to create analysis job");
      await refreshPoints().catch(() => undefined);
    }
  }

  async function retry() {
    if (!job || !user) return;
    if (user.points_balance < 1) {
      setError("Insufficient points");
      return;
    }
    setError("");
    const queued = await retryJob(job.id);
    setJob(queued);
    await refreshPoints();
    await poll(queued.id);
  }

  const busy = job?.status === "queued" || job?.status === "running";

  if (!user) {
    return (
      <div className="app-shell auth-shell">
        <main className="auth-page">
          <section className="auth-card">
            <div>
              <span className="hero-tag">ProductLens</span>
              <h1>User account required</h1>
              <p>Register to receive 10 points. Each complete product analysis costs 1 point.</p>
            </div>
            <form className="auth-form" onSubmit={submitAuth}>
              <div className="auth-tabs">
                <button type="button" className={authMode === "login" ? "active" : ""} onClick={() => setAuthMode("login")}>Login</button>
                <button type="button" className={authMode === "register" ? "active" : ""} onClick={() => setAuthMode("register")}>Register</button>
              </div>
              <label>Email</label>
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
              {authMode === "register" && (
                <>
                  <label>Username</label>
                  <input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Optional" />
                </>
              )}
              <label>Password</label>
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={authMode === "register" ? 8 : 1} required />
              <button type="submit">{authMode === "register" ? "Create account" : "Login"}</button>
              {error && <div className="error-banner compact" role="alert">{error}</div>}
            </form>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top"><span>PA</span><strong>Product<span>Lens</span></strong></a>
        <div className="userbar">
          <span className={`mode-badge ${mode}`}><i />{mode === "live" ? "Live API" : mode === "demo" ? "Demo" : "Offline"}</span>
          <strong>{user.points_balance} points</strong>
          <span>{user.email}</span>
          <button onClick={signOut}>Logout</button>
        </div>
      </header>

      <main id="top">
        <section className="hero">
          <span className="hero-tag">AI product analysis</span>
          <h1>Turn product links into evidence-based content</h1>
          <p>Submit an Amazon product link. The system stores history in MySQL and encrypts product facts before writing them to the database.</p>
          <form className="url-form" onSubmit={submit}>
            <label htmlFor="amazon-url">Amazon product URL</label>
            <div className="url-input-wrap">
              <input id="amazon-url" type="url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://amazon.com/dp/..." required />
              <button type="submit" disabled={busy || user.points_balance < 1}>{busy ? "Analyzing..." : "Start analysis"}</button>
            </div>
            <div className="form-actions">
              <button className="demo-link" type="button" onClick={() => setUrl(demoUrl)}>Use sample link</button>
              <span>Cost: 1 point per analysis</span>
            </div>
          </form>
          {error && <div className="error-banner" role="alert"><strong>Action failed</strong><span>{error}</span></div>}
        </section>

        {job && !job.result && job.status !== "failed" && <ProgressTimeline stage={job.stage} progress={job.progress} />}
        {job && job.trace_events.length > 0 && <AnalysisTrace events={job.trace_events} />}
        {job?.status === "failed" && <div className="error-banner result-error" role="alert"><strong>Analysis failed</strong><span>{job.error}</span><button onClick={retry}>Retry</button></div>}

        {job?.result && (
          <div className="results">
            <ProductSummary facts={job.result.facts} />
            <InsightGrid analysis={job.result.analysis} />
            <div className="final-grid">
              <ScriptPanel script={job.result.analysis.voiceover} />
              <QualityPanel report={job.result.quality} />
            </div>
          </div>
        )}
      </main>
      <footer><span>ProductLens</span><span>User accounts and points are stored in MySQL.</span></footer>
    </div>
  );
}
