const stages = [
  ["VALIDATING", "校验链接"],
  ["FETCHING_PRODUCT", "提取商品信息"],
  ["ANALYZING_IMAGES", "理解商品图片"],
  ["ANALYZING_PRODUCT", "分析用户与卖点"],
  ["CHECKING_QUALITY", "检查事实与文案"],
  ["COMPLETED", "生成报告"],
] as const;

export function ProgressTimeline({ stage, progress }: { stage: string; progress: number }) {
  const activeIndex = Math.max(0, stages.findIndex(([key]) => key === stage));
  return (
    <section className="progress-card" aria-live="polite">
      <div className="progress-heading">
        <div>
          <span className="eyebrow">AI WORKFLOW</span>
          <h2>正在理解这件商品</h2>
        </div>
        <strong>{progress}%</strong>
      </div>
      <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
      <ol className="timeline">
        {stages.map(([key, label], index) => (
          <li className={index < activeIndex || stage === "COMPLETED" ? "done" : index === activeIndex ? "active" : ""} key={key}>
            <span className="timeline-dot">{index < activeIndex || stage === "COMPLETED" ? "✓" : index + 1}</span>
            <span>{label}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

