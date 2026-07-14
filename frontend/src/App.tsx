import { FormEvent, useEffect, useRef, useState } from "react";

import { createJob, getJob, retryJob } from "./api";
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

  useEffect(() => () => { if (pollRef.current) window.clearTimeout(pollRef.current); }, []);

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
        <div className="mode-badge"><i /> Demo Ready</div>
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
