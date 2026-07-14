from app.models import ProductAnalysis, ProductFacts
from app.url_parser import AmazonLink
from urllib.parse import quote


DEMO_CHAIR_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 900 760'>
<defs><linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'><stop stop-color='#e8eee7'/><stop offset='1' stop-color='#d9e6dc'/></linearGradient><filter id='s'><feDropShadow dx='0' dy='18' stdDeviation='18' flood-opacity='.18'/></filter></defs>
<rect width='900' height='760' rx='42' fill='url(#bg)'/><ellipse cx='452' cy='656' rx='275' ry='42' fill='#315b4c' opacity='.12'/>
<g filter='url(#s)' stroke-linecap='round' stroke-linejoin='round'>
<path d='M270 270L350 548H610L676 270' fill='#166849' stroke='#103e31' stroke-width='18'/><path d='M296 310Q448 240 651 304L610 548H350Z' fill='#227957'/>
<path d='M286 278Q450 200 670 270L704 158Q476 84 246 170Z' fill='#bff263' stroke='#103e31' stroke-width='16'/><path d='M270 278L240 112M676 270L712 108' fill='none' stroke='#173c31' stroke-width='18'/>
<path d='M354 548L245 664M602 548L704 664M343 548L424 665M612 548L525 665' fill='none' stroke='#173c31' stroke-width='22'/>
<path d='M280 402H205Q184 402 184 426V491Q184 510 205 510H305M666 402H736Q758 402 758 426V491Q758 510 736 510H641' fill='none' stroke='#173c31' stroke-width='18'/>
<circle cx='232' cy='451' r='28' fill='#f7fbf6' stroke='#173c31' stroke-width='12'/>
</g><text x='450' y='715' text-anchor='middle' font-family='Arial,sans-serif' font-weight='700' font-size='24' fill='#315b4c'>DEMO PRODUCT · CAMP CHAIR</text></svg>"""
DEMO_CHAIR_DATA_URL = "data:image/svg+xml;charset=UTF-8," + quote(DEMO_CHAIR_SVG)


class DemoProductProvider:
    def fetch(self, link: AmazonLink) -> ProductFacts:
        return ProductFacts(
            asin=link.asin,
            title="VTOY 便携折叠露营椅（带遮阳篷）",
            category="户外露营椅",
            price="$89.99",
            currency="USD",
            rating=4.4,
            review_count=286,
            features=["可折叠设计", "可调节遮阳篷", "双侧杯架", "加宽坐面"],
            specifications={"承重": "300 lb", "材质": "牛津布与钢管", "适用场景": "露营、庭院、观赛"},
            images=[DEMO_CHAIR_DATA_URL],
            source_url=link.canonical_url,
        )


class DemoVisionProvider:
    def analyze(self, images: list[str]) -> list[str]:
        if not images:
            return []
        return [
            "主图可见椅背上方连接一体式遮阳篷",
            "座椅左右两侧均有杯架或收纳袋",
            "折叠钢管支架适合户外搬运，图片未提供折叠后尺寸",
        ]


class DemoTextModel:
    def analyze(self, facts: ProductFacts, visual_findings: list[str]) -> ProductAnalysis:
        return ProductAnalysis(
            target_users=["周末露营和观赛人群", "需要户外遮阳的家庭用户", "偏好一体化装备的轻度户外玩家"],
            scenarios=["露营营地休息", "庭院午后", "户外赛事或垂钓"],
            pain_points=["普通折叠椅缺少头顶遮挡", "饮料和小物件无处放", "临时休息装备携带麻烦"],
            selling_points=["可折叠设计", "可调节遮阳篷", "双侧杯架", "加宽坐面"],
            visual_findings=visual_findings,
            voiceover="户外坐下就被太阳追着晒？这把折叠椅把遮阳篷、加宽坐面和双侧杯架做在一起，打开就能休息，收起方便带走，适合露营、庭院和户外观赛。",
        )

    def revise(self, facts: ProductFacts, analysis: ProductAnalysis, issue_messages: list[str]) -> ProductAnalysis:
        return analysis.model_copy(
            update={
                "selling_points": [point for point in analysis.selling_points if point in facts.features],
                "voiceover": analysis.voiceover[:150],
            }
        )
