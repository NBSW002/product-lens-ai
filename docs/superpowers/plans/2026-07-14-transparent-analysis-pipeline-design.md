# 可追溯商品分析流水线设计

## 背景与目标

当前 Live 模式能够从 Rainforest 获取商品字段，并调用 Qwen Vision 与 DeepSeek，但页面只展示最终结果。用户无法判断字段来源、模型原始输出及质量检查依据，自动修订还可能通过清空内容规避质量问题。

本次改造在现有结果页内增加实时、可展开的分析流水线，完整呈现每个阶段的脱敏输入、结构化输出、耗时、状态、错误与修订差异。同时修复空分析得到 88 分并显示通过的问题，使最终结论可追溯到商品事实或图片证据。

任务与追踪记录仅使用现有内存存储，后端重启后清空，不引入数据库。

## 已确认的产品决策

- 透明度：完整证据链，但不保存第三方完整原始响应。
- 展示：现有结果页内的可展开流水线。
- 生命周期：仅当前后端运行期间保留。
- DeepSeek 初稿与修订稿必须分别保存，修订不得覆盖初稿。
- API Key、Authorization 请求头及其他认证信息不得进入追踪记录或前端响应。

## 用户体验

“分析过程”位于商品输入区下方、最终商品卡片上方。创建任务后立即出现六个固定步骤：商品抓取、图片分析、DeepSeek 初稿、质量检查、自动修订、最终结果。

每步显示等待中、运行中、成功、失败或跳过，以及开始时间和实际耗时。点击展开后展示服务商、模型、脱敏输入摘要、结构化输出、字段来源、质量问题或错误。初稿一次通过时，自动修订显示为跳过并解释原因。外部服务失败时保留此前成功步骤，不能用空白结果伪装成功。

页面顶部模式徽标由后端健康接口驱动：`live` 显示“真实 API”，`demo` 显示“演示模式”，不再硬编码 `Demo Ready`。

## 后端数据模型

为 `Job` 增加 `trace_events`。每个 `TraceEvent` 包含：

- `id`：事件唯一标识。
- `stage`：`PRODUCT_FETCH`、`VISION_ANALYSIS`、`TEXT_DRAFT`、`QUALITY_CHECK`、`TEXT_REVISION` 或 `FINALIZE`。
- `title`：中文阶段名。
- `status`：`pending`、`running`、`completed`、`failed` 或 `skipped`。
- `provider`：`Rainforest`、`Qwen`、`DeepSeek` 或 `Internal`。
- `model`：模型名称；非模型阶段为 `null`。
- `started_at`、`finished_at`、`duration_ms`。
- `input`：脱敏并限制体积的 JSON 对象。
- `output`：结构化 JSON 对象，不含认证信息。
- `field_sources`：输出字段到来源字段的映射。
- `error`：安全、可读的错误；成功步骤为 `null`。

事件保存在 `JobRepository` 的内存任务对象中。Repository 提供阶段开始、完成、失败和跳过的更新方法，避免后台任务执行时丢失已产生记录。

## 数据流与证据链

### 商品抓取

输入记录 ASIN、Amazon 域名和规范化 URL，不记录 Rainforest API Key。输出记录实际采用的 `ProductFacts`。字段来源至少包括：

- `title` ← `product.title`
- `category` ← `product.categories[-1].name`
- `price` ← `product.buybox_winner.price`，缺失时回退 `product.price`
- `rating` ← `product.rating`
- `review_count` ← `product.ratings_total`
- `features` ← `product.feature_bullets`
- `specifications` ← `product.specifications`
- `images` ← `product.images_flat`，缺失时回退 `product.images[].link`

追踪展示图片数量和实际 URL，前端默认折叠 URL 细节。解析器验证响应 ASIN 与请求 ASIN 一致；不一致时阶段失败。价格统一转为显示字符串，同时保留货币字段。数组和规格只接受预期类型，避免第三方结构变化产生错误映射。

### 图片分析

输入记录送入 Qwen 的图片 URL（最多六张）和模型名，输出记录 `findings`。商品有图片但模型返回空数组时阶段失败；商品无图片时显示“商品数据未提供可分析图片”，不继续生成看似完整的分析。

### DeepSeek 初稿

输入记录商品事实、图片观察和 JSON 字段要求，不记录请求头。输出保存完整 `ProductAnalysis` 初稿。模型响应同时通过结构校验和内容完整性校验：四个洞察列表、图片观察和口播均不得为空。

### 质量检查与修订

质量检查输出每个问题的代码、严重级别、扣分、说明和建议，并展示证据覆盖率。新增高严重级别问题：`EMPTY_TARGET_USERS`、`EMPTY_SCENARIOS`、`EMPTY_PAIN_POINTS`、`EMPTY_SELLING_POINTS`、`EMPTY_VISUAL_FINDINGS`、`EMPTY_VOICEOVER`。

任何完整性问题均不得通过；核心内容全部为空时分数为 0；覆盖率为 0 时不得显示通过。

初稿未通过时仅调用一次 DeepSeek 修订。修订输入包含商品事实、初稿和问题列表；初稿事件保持不变，修订稿写入独立事件并再次质量检查。修订仍不通过时任务失败，保留两版内容和全部问题，不做无上限重试。

### 最终结果

仅最终质量检查通过时，`FINALIZE` 完成并写入 `AnalysisResult`。否则 `FINALIZE` 失败、任务状态为 `failed`，前端仍显示已经取得的商品事实和完整流水线。

## 安全与体积控制

- 追踪事件由应用显式构造，不保存 HTTP 请求对象、请求头或环境变量。
- 递归脱敏键名包含 `api_key`、`authorization`、`token`、`secret` 和 `password`。
- 单个文本值和列表长度受限，避免任务响应无限膨胀。
- Provider 错误只暴露安全说明和 HTTP 状态码，不返回包含密钥的请求 URL。

## 前端组件

新增 `AnalysisTrace` 作为流水线容器，`TraceStep` 负责单个可展开步骤。组件使用原生按钮和 `aria-expanded`，支持键盘操作。运行中及失败步骤自动展开；完成步骤折叠但保留摘要。

轮询沿用现有任务查询接口，每次响应更新 `trace_events`，不增加 WebSocket。最终结果在任务成功前不渲染空卡片；失败时显示已完成阶段与失败原因。

## 错误处理

- Rainforest 无商品、ASIN 不一致或结构异常：商品抓取失败，后续步骤跳过。
- Qwen 调用失败或观察为空：图片分析失败，后续步骤跳过。
- DeepSeek HTTP、JSON 或完整性失败：初稿或修订失败并保留安全错误。
- 初稿质量不通过：执行一次修订。
- 修订仍不通过：任务失败并展示两轮问题。
- 前端无法连接后端：显示连接错误，不把模式默认成 Demo。

## 测试策略

后端测试覆盖 Rainforest 字段映射和来源、ASIN 不一致、事件生命周期与顺序、递归脱敏、空内容质量失败、初稿保留、修订失败以及 Provider 失败后的事件可读性。

前端测试覆盖六步顺序、展开详情、失败和跳过原因、动态 Live/Demo 徽标，以及任务失败时只显示流水线而不显示空洞察卡片。

最终运行后端完整测试、前端完整测试和生产构建，并在本地浏览器验证 Demo 流程。真实 API 内容质量由用户用自己的密钥执行一次商品分析验证，测试和日志不得打印密钥。

## 验收标准

1. 分析运行时实时显示当前步骤。
2. 任一步骤可追溯脱敏输入和结构化输出。
3. 页面和 API 响应不包含认证信息。
4. 空分析不可能获得 88 分或显示通过。
5. 商品字段可追溯到 Rainforest 字段路径。
6. DeepSeek 修订不覆盖或隐藏初稿。
7. 外部服务失败时保留此前成功的数据和步骤。
8. 模式徽标准确反映后端状态。
9. 后端重启后任务和追踪记录清空。

