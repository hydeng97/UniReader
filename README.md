# 论文阅读助手 (Paper Reading Assistant)

一个基于大语言模型的智能论文阅读辅助工具，支持 PDF/Markdown 文档解析、多角度论文解读、分支式对话管理。

## 功能特点

### 核心功能

- **智能文档解析**
  - 支持 PDF 和 Markdown 文件上传
  - 支持公网 URL 直接解析
  - MinerU API 高质量 PDF 解析（支持公式、表格识别）
  - 本地 PyMuPDF 解析作为备选方案
  - **自动下载 PDF 备份到本地**
  - **解析结果保存为 Markdown 格式**
  - **自动提取论文标题**（基于 LLM）

- **多角度论文解读**
  - 预设多种解读提示词（通用解读、通俗解读、技术细节等）
  - 可自定义添加解读模板
  - 并行请求多个解读角度，提高效率

- **分支式对话管理**
  - 每个解读角度独立分支，互不干扰
  - 支持基于解读内容继续提问
  - 支持分支总结和汇总
  - **解析完成后即可手动创建分支**

- **批量导入**
  - 支持 JSON 格式批量导入论文列表
  - 自动转换 arXiv/OpenReview 链接
  - 并发导入，显示进度

- **友好的交互体验**
  - 实时流式输出，打字机效果
  - Markdown 渲染（支持代码高亮）
  - KaTeX 数学公式渲染
  - 停止生成功能
  - 切换文档时保持对话状态

### 技术优势

- **纯原生实现**：前端使用原生 HTML/CSS/JavaScript，无需 Node.js 构建
- **轻量后端**：基于 FastAPI，启动简单，资源占用低
- **流式响应**：SSE 实时推送，响应迅速
- **状态保持**：支持切换文档时保持对话状态
- **多 API 支持**：兼容 OpenAI、DeepSeek 等多种 LLM API

## 快速开始

### 环境要求

- Python 3.8+
- 支持 conda 环境

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd read_paper
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

或使用 conda：
```bash
conda create -n paper_reader python=3.10
conda activate paper_reader
pip install -r requirements.txt
```

3. **配置文件**

复制配置模板并编辑：
```bash
cp config.yaml.template config.yaml
```

编辑 `config.yaml`，填入您的 API 配置：
```yaml
llm_apis:
  - name: "OpenAI"
    base_url: "https://api.openai.com/v1"
    api_key: "your-api-key"
    model: "gpt-4"
    is_default: true

mineru:
  - name: "MinerU"
    token: "your-mineru-token"  # 可选，从 https://mineru.net 获取
    is_default: true
```

4. **启动服务**
```bash
python run.py
```

5. **访问应用**

打开浏览器访问 `http://localhost:8000`

## 使用方法

### 上传论文

1. **本地上传**：点击上传区域，选择 PDF 或 Markdown 文件
2. **URL 解析**：输入公网可访问的 PDF 链接（推荐）

> 推荐：使用公网 URL 可获得更好的解析效果（MinerU API 支持公式、表格识别）

### 论文解读

1. 上传论文后，点击 **"开始分析"** 按钮
2. 系统会根据预设的提示词并行生成多个解读分支
3. 每个分支独立展示不同角度的解读内容

### 对话问答

1. 在任意分支中输入问题，与 AI 进行对话
2. 对话基于论文内容，AI 会引用相关内容回答
3. 可以切换分支查看不同角度的讨论

### 其他功能

- **新建分支**：手动创建新的对话分支
- **总结分支**：总结当前分支的对话内容
- **总结全部**：汇总所有分支的讨论要点
- **编辑标题**：修改论文显示名称

## 项目结构

```
read_paper/
├── backend/                 # 后端模块
│   ├── __init__.py
│   ├── config_manager.py    # 配置管理
│   ├── conversation.py      # 对话树管理
│   ├── llm_client.py        # LLM API 客户端
│   ├── mineru_client.py     # MinerU API 客户端
│   ├── models.py            # 数据模型
│   └── pdf_parser.py        # 本地 PDF 解析
├── static/
│   └── index.html           # 前端单页应用
├── data/                    # 数据存储目录
│   └── papers/              # 论文数据
│       └── {paper_id}/
│           ├── {title}.pdf  # 原始 PDF 备份（以标题命名）
│           ├── content.md   # 解析内容 (Markdown)
│           ├── session.json # 会话状态
│           └── conversation.json  # 对话记录
├── config.yaml              # 用户配置
├── config.yaml.template     # 配置模板
├── main.py                  # FastAPI 主程序
├── run.py                   # 启动脚本
├── requirements.txt         # 依赖列表
├── README.md                # 项目说明
└── GUIDE.md                 # 详细使用指南
```

## 配置说明

### LLM API 配置

支持多个 API 配置，可以切换使用：

```yaml
llm_apis:
  - name: "OpenAI"
    base_url: "https://api.openai.com/v1"
    api_key: "sk-xxx"
    model: "gpt-4"
    is_default: true
  
  - name: "DeepSeek"
    base_url: "https://api.deepseek.com/v1"
    api_key: "sk-xxx"
    model: "deepseek-chat"
    is_default: false
```

| 字段 | 说明 |
|------|------|
| name | 配置名称，用于界面显示 |
| base_url | API 基础 URL |
| api_key | API 密钥 |
| model | 使用的模型名称 |
| is_default | 是否为默认配置 |

### MinerU 配置

MinerU 提供高质量的 PDF 解析服务：

```yaml
mineru:
  - name: "MinerU"
    token: "your-token"
    is_default: true
```

- 获取 Token：访问 [https://mineru.net](https://mineru.net) 注册并获取
- 如不配置，系统会自动使用本地 PyMuPDF 解析

### 提示词配置

可以自定义论文解读的提示词：

```yaml
prompts:
  - name: "我的解读"
    prompt: |
      请从以下角度解读这篇论文...
    is_enabled: true
```

| 字段 | 说明 |
|------|------|
| name | 提示词名称，显示为分支名 |
| prompt | 发送给 LLM 的提示词内容 |
| is_enabled | 是否启用 |

### 服务器配置

```yaml
server:
  host: "0.0.0.0"      # 监听地址
  port: 8000           # 主服务端口
  file_server_port: 8765  # 文件服务端口
```

## 技术实现

### 架构概述

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Paper List  │  │  Branches   │  │   Chat Messages    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                         │ SSE                                │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    API Endpoints                     │    │
│  │  /api/papers/*  /api/extract  /api/analyze  /api/ask │    │
│  └─────────────────────────────────────────────────────┘    │
│                         │                                    │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐  │
│  │ LLMClient│  │ MinerU    │  │ PDF Parser│  │ Config   │  │
│  │          │  │ Client    │  │ (PyMuPDF) │  │ Manager  │  │
│  └──────────┘  └───────────┘  └───────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   LLM API          MinerU API         Local FS
   (OpenAI)         (Optional)         (Data)
```

### 关键技术

1. **流式响应**
   - 后端使用 SSE (Server-Sent Events) 推送数据
   - 前端使用 EventSource 接收实时数据
   - 支持多分支并行流式输出

2. **状态管理**
   - 前端使用 Map 保存每个文档的状态
   - 支持切换文档时保持对话状态
   - 后端持久化到 JSON 文件

3. **PDF 解析**
   - 优先使用 MinerU API（支持公式、表格）
   - 失败时自动回退到本地 PyMuPDF
   - 支持直接输入公网 URL

4. **对话树管理**
   - 每个分支独立管理消息历史
   - 支持消息的父子关系
   - 构建完整的对话上下文

### API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/papers` | GET | 获取论文列表 |
| `/api/papers` | POST | 上传论文 |
| `/api/papers/{id}` | GET | 获取论文详情 |
| `/api/papers/extract-url` | POST | 从 URL 解析论文 |
| `/api/papers/{id}/extract` | GET | 提取论文内容 (SSE) |
| `/api/papers/{id}/analyze` | GET | 分析论文 (SSE) |
| `/api/papers/{id}/ask` | POST | 提问 (SSE) |
| `/api/papers/{id}/branches` | GET | 获取分支列表 |
| `/api/papers/{id}/branches/{bid}` | DELETE | 删除分支 |
| `/api/papers/{id}/create-branch` | POST | 创建分支 |
| `/api/config` | GET/POST | 获取/保存配置 |

## 常见问题

### Q: PDF 解析失败怎么办？

A: 
1. 推荐使用公网可访问的 PDF URL（如 arXiv 链接）
2. 检查 MinerU Token 是否正确配置
3. 系统会自动回退到本地解析器

### Q: 如何添加新的 LLM API？

A: 在配置文件中添加新的 API 配置项，确保 `base_url` 符合 OpenAI API 格式。

### Q: 为什么有些公式渲染不正确？

A: 
1. MinerU 解析效果更好，推荐配置使用
2. 本地解析器对复杂公式支持有限

### Q: 如何备份数据？

A: 复制 `data/` 目录即可备份所有论文和对话记录。

## 开发计划

- [x] PDF 备份和 Markdown 存储
- [x] 自动提取论文标题
- [x] 批量导入论文
- [ ] 支持更多 PDF 解析服务
- [ ] 添加论文导出功能
- [ ] 添加论文相似度分析
- [ ] 支持协作阅读

## 详细使用指南

请参阅 [GUIDE.md](./GUIDE.md) 获取详细的功能说明和操作指南。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
