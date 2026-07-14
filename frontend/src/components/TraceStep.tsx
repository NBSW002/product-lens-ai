import { useState } from "react";

import type { TraceEvent, TraceStatus } from "../types";

const statusLabels: Record<TraceStatus, string> = {
  pending: "等待中",
  running: "运行中",
  completed: "成功",
  failed: "失败",
  skipped: "跳过",
};

function JsonBlock({ title, value }: { title: string; value: Record<string, unknown> }) {
  if (Object.keys(value).length === 0) return null;
  return <section className="trace-data"><h4>{title}</h4><pre>{JSON.stringify(value, null, 2)}</pre></section>;
}

export function TraceStep({ event }: { event: TraceEvent }) {
  const [expanded, setExpanded] = useState(event.status === "running" || event.status === "failed");
  return (
    <article className={`trace-step ${event.status}`}>
      <button type="button" className="trace-toggle" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
        <span className="trace-dot" aria-hidden="true" />
        <span className="trace-title"><strong>{event.title}</strong><small>{event.provider}{event.model ? ` · ${event.model}` : ""}</small></span>
        <span className={`trace-status ${event.status}`}>{statusLabels[event.status]}</span>
        <span className="trace-duration">{event.duration_ms === null ? "—" : `${event.duration_ms} ms`}</span>
        <span className="trace-chevron" aria-hidden="true">{expanded ? "−" : "+"}</span>
      </button>
      {expanded && (
        <div className="trace-details">
          <div className="trace-meta"><span>服务：<b>{event.provider}</b></span>{event.model && <span>模型：<b>{event.model}</b></span>}</div>
          {event.error && <div className="trace-error" role={event.status === "failed" ? "alert" : undefined}>{event.error}</div>}
          <JsonBlock title="阶段输入" value={event.input} />
          <JsonBlock title="结构化输出" value={event.output} />
          {Object.keys(event.field_sources).length > 0 && (
            <section className="trace-sources"><h4>字段来源</h4><dl>{Object.entries(event.field_sources).map(([field, source]) => <div key={field}><dt>{field}</dt><dd>{source}</dd></div>)}</dl></section>
          )}
        </div>
      )}
    </article>
  );
}

