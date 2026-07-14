import { useState } from "react";

export function ScriptPanel({ script }: { script: string }) {
  const [copied, setCopied] = useState(false);
  async function copyScript() {
    await navigator.clipboard.writeText(script);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }
  return (
    <section className="script-card section-card">
      <div className="script-topline">
        <div><span className="eyebrow">SHORT VIDEO SCRIPT</span><h2>短视频口播文案</h2></div>
        <span className="char-count">{script.replace(/\s/g, "").length} / 150 字</span>
      </div>
      <blockquote>{script}</blockquote>
      <div className="script-footer">
        <span><i /> 前 5 秒钩子</span>
        <button className="secondary-button" type="button" onClick={copyScript}>{copied ? "已复制" : "复制文案"}</button>
      </div>
    </section>
  );
}

