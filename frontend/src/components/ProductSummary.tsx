import type { ProductFacts } from "../types";

export function ProductSummary({ facts }: { facts: ProductFacts }) {
  return (
    <section className="product-card section-card">
      <div className="product-media">
        {facts.images[0] ? <img src={facts.images[0]} alt={facts.title} /> : <div className="image-placeholder">暂无商品图</div>}
        <span className="source-badge">Amazon · {facts.asin}</span>
      </div>
      <div className="product-copy">
        <span className="eyebrow">PRODUCT SNAPSHOT</span>
        <p className="category">{facts.category}</p>
        <h2>{facts.title}</h2>
        <div className="product-metrics">
          {facts.price && <strong>{facts.price}</strong>}
          {facts.rating && <span>★ {facts.rating} <small>({facts.review_count ?? 0})</small></span>}
        </div>
        <div className="chip-row">
          {facts.features.slice(0, 5).map((feature) => <span className="chip" key={feature}>{feature}</span>)}
        </div>
        <dl className="spec-list">
          {Object.entries(facts.specifications).slice(0, 5).map(([name, value]) => (
            <div key={name}><dt>{name}</dt><dd>{value}</dd></div>
          ))}
        </dl>
        <a className="source-link" href={facts.source_url} target="_blank" rel="noreferrer">查看原始商品页 ↗</a>
      </div>
    </section>
  );
}

