import type { ProductAnalysis } from "../types";

const cards = [
  ["目标用户", "◎", "target_users"],
  ["使用场景", "◇", "scenarios"],
  ["用户痛点", "!", "pain_points"],
  ["核心卖点", "↗", "selling_points"],
] as const;

export function InsightGrid({ analysis }: { analysis: ProductAnalysis }) {
  return (
    <section>
      <div className="section-title">
        <div><span className="eyebrow">PRODUCT INTELLIGENCE</span><h2>产品洞察</h2></div>
        <p>基于商品事实与图片证据综合推导</p>
      </div>
      <div className="insight-grid">
        {cards.map(([title, icon, key]) => (
          <article className="insight-card" key={key}>
            <span className="insight-icon">{icon}</span>
            <h3>{title}</h3>
            <ul>{analysis[key].map((item) => <li key={item}>{item}</li>)}</ul>
          </article>
        ))}
      </div>
      <article className="vision-card">
        <div><span className="vision-mark">◉</span><div><span className="eyebrow">QWEN VISION</span><h3>图片观察</h3></div></div>
        <ul>{analysis.visual_findings.map((item) => <li key={item}>{item}</li>)}</ul>
      </article>
    </section>
  );
}

