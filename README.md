# ProductLens — AI 产品分析助手

输入公开的 Amazon 商品链接，系统会整理商品事实、理解商品图片、分析用户与场景、生成 150 字以内的中文短视频口播，并执行事实一致性和夸大宣传检查。

## 已实现能力

- 严格校验 Amazon 域名并提取 ASIN，避免任意 URL 请求风险
- 分阶段任务：链接校验 → 商品数据 → 图片理解 → 产品分析 → 质量检查 → 自动修订
- DeepSeek V4 文本分析，支持结构化 JSON 输出
- 阿里云百炼 Qwen3-VL 商品图片理解
- 商品数据、视觉模型和文本模型均采用独立适配器
- 对无依据卖点、绝对化宣传、弱钩子和超过 150 字进行质量检查
- React 响应式界面，包含任务进度、产品概览、洞察、图片观察、口播和质量评分
- 无密钥 Demo 模式，可完整演示全部流程

## 项目结构

```text
backend/
  app/
    providers/       # Demo 与真实 API 适配器
    jobs.py           # 任务状态仓库
    main.py           # FastAPI 路由
    models.py         # 领域模型
    quality.py        # 确定性质量门
    service.py        # 分阶段分析流水线
    url_parser.py     # Amazon 链接安全校验
  tests/
frontend/
  src/
    components/       # 结果与进度组件
    App.tsx
    api.ts
docs/superpowers/plans/
```

## 本地运行

### 1. 启动后端

系统已有 Python 时：

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

当前机器也可以直接使用 Anaconda Python：

```powershell
cd backend
C:\Users\Administrator\anaconda3\python.exe -m uvicorn app.main:app --reload --port 8000
```

### 2. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

访问 `http://127.0.0.1:5173`，点击“使用示例商品”即可完整体验 Demo 流程。

## 使用真实 API

复制 `backend/.env.example` 为环境变量配置，并设置：

```text
APP_MODE=live
RAINFOREST_API_KEY=...
DASHSCOPE_API_KEY=...
DEEPSEEK_API_KEY=...
```

当前商品数据适配器使用 Rainforest API；视觉分析使用阿里云百炼 `qwen3-vl-plus`；文本分析使用 `deepseek-v4-flash`。所有密钥仅由后端读取，不会下发到浏览器。

## 测试与构建

```powershell
# 后端
cd backend
$env:PYTHONPATH=(Get-Location).Path
C:\Users\Administrator\anaconda3\python.exe -m pytest -v

# 前端
cd frontend
npm test -- --run
npm run build
```

## 设计取舍

- 本地版本使用线程安全的内存任务仓库，减少笔试项目的部署负担；生产环境可替换为 Redis/Celery。
- Demo 模式固定返回可复现结果，便于无密钥评审；Live 模式走相同领域模型与质量门。
- 模型输出不是最终事实来源。质量门会基于商品字段和图片观察检查卖点，问题内容最多自动修订一次。
- 部署平台暂未绑定，前端可静态部署，后端可容器化部署到国内云或国际区域。

