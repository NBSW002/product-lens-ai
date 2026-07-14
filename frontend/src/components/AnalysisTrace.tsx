import type { TraceEvent } from "../types";
import { TraceStep } from "./TraceStep";

export function AnalysisTrace({ events }: { events: TraceEvent[] }) {
  return (
    <section className="analysis-trace" aria-labelledby="analysis-trace-title">
      <div className="section-title trace-heading">
        <div><span className="eyebrow">AUDIT TRAIL</span><h2 id="analysis-trace-title">分析过程</h2></div>
        <p>每一步输入、输出与证据来源均可展开追溯</p>
      </div>
      <div className="trace-list">{events.map((event) => <TraceStep event={event} key={event.id} />)}</div>
    </section>
  );
}
