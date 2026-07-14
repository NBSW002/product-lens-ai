import re

from app.models import ProductAnalysis, ProductFacts, QualityIssue, QualityReport


EXAGGERATION_TERMS = (
    "全球第一",
    "百分百",
    "100%",
    "绝对",
    "最强",
    "永久",
    "错过后悔",
    "闭眼入",
)


def chinese_length(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _normalized(text: str) -> str:
    return re.sub(r"[\s，。！？、：；,.!?%\-]", "", text.lower()).replace("带", "")


class QualityChecker:
    def check(self, facts: ProductFacts, analysis: ProductAnalysis) -> QualityReport:
        issues: list[QualityIssue] = []
        required_content = (
            ("EMPTY_TARGET_USERS", analysis.target_users, "目标用户为空。"),
            ("EMPTY_SCENARIOS", analysis.scenarios, "使用场景为空。"),
            ("EMPTY_PAIN_POINTS", analysis.pain_points, "用户痛点为空。"),
            ("EMPTY_SELLING_POINTS", analysis.selling_points, "核心卖点为空。"),
            ("EMPTY_VISUAL_FINDINGS", analysis.visual_findings, "图片观察为空。"),
            ("EMPTY_VOICEOVER", analysis.voiceover.strip(), "短视频口播为空。"),
        )
        for code, value, message in required_content:
            if not value:
                issues.append(
                    QualityIssue(
                        code=code,
                        severity="high",
                        message=message,
                        suggestion="补充有商品事实或图片证据支持的内容。",
                    )
                )
        evidence = " ".join(
            [
                facts.title,
                facts.category,
                *facts.features,
                *facts.specifications.keys(),
                *facts.specifications.values(),
                *analysis.visual_findings,
            ]
        )
        normalized_evidence = _normalized(evidence)

        if any(term.lower() in analysis.voiceover.lower() or term.lower() in " ".join(analysis.selling_points).lower() for term in EXAGGERATION_TERMS):
            issues.append(
                QualityIssue(
                    code="EXAGGERATION",
                    severity="high",
                    message="文案包含绝对化或无法验证的夸张表达。",
                    suggestion="改为可由商品信息支持的具体描述。",
                )
            )

        grounded = 0
        for claim in analysis.selling_points:
            normalized_claim = _normalized(claim)
            claim_grounded = bool(normalized_claim) and (
                normalized_claim in normalized_evidence
                or any(_normalized(token) in normalized_evidence for token in re.split(r"[，、并且和]", claim) if len(_normalized(token)) >= 2)
            )
            if claim_grounded:
                grounded += 1
            else:
                issues.append(
                    QualityIssue(
                        code="UNSUPPORTED_CLAIM",
                        severity="high",
                        message=f"卖点“{claim}”未在商品事实或图片观察中找到依据。",
                        suggestion="删除该说法，或补充可信数据来源。",
                    )
                )

        if chinese_length(analysis.voiceover) > 150:
            issues.append(
                QualityIssue(
                    code="SCRIPT_TOO_LONG",
                    severity="medium",
                    message="口播文案超过 150 字。",
                    suggestion="删减背景描述，只保留钩子、核心卖点和场景。",
                )
            )

        opening = analysis.voiceover[:28]
        if not any(marker in opening for marker in ("？", "?", "还在", "是不是", "一坐下", "没想到")):
            issues.append(
                QualityIssue(
                    code="WEAK_HOOK",
                    severity="medium",
                    message="开头缺少明确的用户痛点或悬念。",
                    suggestion="前 5 秒使用问题、反差或具体痛点切入。",
                )
            )

        deductions = {"low": 5, "medium": 12, "high": 24}
        all_empty = not any(value for _, value, _ in required_content)
        score = 0 if all_empty else max(0, 100 - sum(deductions[issue.severity] for issue in issues))
        coverage = round(grounded / max(1, len(analysis.selling_points)) * 100)
        return QualityReport(
            score=score,
            passed=score >= 80 and coverage > 0 and not any(issue.severity == "high" for issue in issues),
            evidence_coverage=coverage,
            issues=issues,
        )
