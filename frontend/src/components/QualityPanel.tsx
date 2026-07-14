import type { QualityReport } from "../types";

export function QualityPanel({ report }: { report: QualityReport }) {
  return (
    <section className="quality-card section-card">
      <div className="quality-score" style={{ "--score": `${report.score * 3.6}deg` } as React.CSSProperties}>
        <div><strong>{report.score}</strong><span>质量评分</span></div>
      </div>
      <div className="quality-copy">
        <div className="quality-heading">
          <div><span className="eyebrow">QUALITY GATE</span><h2>{report.passed ? "内容通过质量检查" : "内容需要关注"}</h2></div>
          <span className={report.passed ? "status-pill pass" : "status-pill warn"}>{report.passed ? "可信发布" : "建议复核"}</span>
        </div>
        <div className="coverage"><span>证据覆盖率</span><strong>{report.evidence_coverage}%</strong><div><i style={{ width: `${report.evidence_coverage}%` }} /></div></div>
        {report.issues.length === 0 ? (
          <p className="quality-note">未发现无依据卖点、绝对化宣传或长度超限。</p>
        ) : (
          <ul className="issue-list">{report.issues.map((issue) => <li key={`${issue.code}-${issue.message}`}><strong>{issue.message}</strong><span>{issue.suggestion}</span></li>)}</ul>
        )}
      </div>
    </section>
  );
}

