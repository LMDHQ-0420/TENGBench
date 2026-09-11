<p align="center">
  <img src="asset/logo.svg" alt="TENGBench 标志" width="520">
</p>

<h1 align="center">TENGBench</h1>

<p align="center">
  面向摩擦纳米发电机科研场景的大语言模型分层测评基准
</p>

> 论文 *TENGBench: Can Large Language Models Understand, Reason about, and Design Triboelectric Nanogenerator-Based Sensors?* 的官方实现。

<p align="center">
  <a href="README.md">English</a> · <a href="#快速开始">快速开始</a> · <a href="#项目结构">项目结构</a>
</p>

## 新闻

- 📊 **[2026/09/11]** 发布 [TENGBench 完整数据集](https://huggingface.co/datasets/LMDHQ-0420/TENGBench)。
- 🚀 **[2026/09/01]** TENGBench 项目代码正式上线。

## 关于

TENGBench 用于评测大语言模型能否理解、推理并设计基于摩擦纳米发电机的传感器。项目通过多智能体框架，从 32 种期刊的 485 篇论文中构建了 4,850 个可追溯问答，覆盖基础理解、应用推理和工程设计三个层级的 10 个子任务，并对来自 7 家厂商的 29 个开源和闭源模型完成了 140,650 次独立问答测评。

全部模型的平均总体得分为 0.5819，最佳模型达到 0.7432。基础理解、应用推理和工程设计的平均得分依次为 0.6828、0.5733 和 0.4894，对应的最佳得分为 0.8299、0.7443 和 0.6554。五个 GPT 模型变体从 Low 提高至 X-high 后，总体得分提升 11.7%–13.3%。

## 完整测评结果

<p align="center">
  <img src="asset/benchmark-results.svg" alt="TENGBench 多模型完整测评结果" width="100%">
</p>

## 数据生成与测评流程

<p align="center">
  <img src="asset/workflow.svg" alt="TENGBench 数据生成与测评流程" width="100%">
</p>

该流程涵盖论文筛选、QA 构建与校验，以及后续基于 API 和 Skill 的模型测评。

## 项目简介

TENGBench 从摩擦纳米发电机（TENG）论文中构建三层问题，并测评大语言模型的科研能力。

<table>
  <thead>
    <tr>
      <th>层级</th>
      <th>评测目标</th>
      <th>子任务</th>
      <th>评测范围</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="4">基础理解<br>（L1）</td>
      <td rowspan="4">评测对 TENG 基础原理与性能指标的掌握程度。</td>
      <td>机理</td>
      <td>接触起电、静电感应、位移电流及其成立条件。</td>
    </tr>
    <tr>
      <td>工作模式</td>
      <td>接触-分离式、滑动式、单电极式和独立层式模式的原理与工作边界。</td>
    </tr>
    <tr>
      <td>摩擦电极性</td>
      <td>摩擦电极性、摩擦电序列以及表面改性的影响。</td>
    </tr>
    <tr>
      <td>性能指标</td>
      <td>电压、电流、转移电荷、功率、负载与阻抗之间的关系和权衡。</td>
    </tr>
    <tr>
      <td rowspan="4">应用推理<br>（L2）</td>
      <td rowspan="4">评测根据材料、结构、运行条件和实验数据推断 TENG 性能变化的能力。</td>
      <td>材料效应</td>
      <td>材料替换、组分、掺杂和表面处理对性能的影响。</td>
    </tr>
    <tr>
      <td>结构效应</td>
      <td>几何形状、层数、电极布局和阵列架构对性能的影响。</td>
    </tr>
    <tr>
      <td>工况影响</td>
      <td>力、频率、湿度、温度和环境条件对性能的影响。</td>
    </tr>
    <tr>
      <td>多步推理</td>
      <td>通过多步推理综合实验观察与定量比较，形成一致结论。</td>
    </tr>
    <tr>
      <td rowspan="2">工程设计<br>（L3）</td>
      <td rowspan="2">评测 TENG 器件与传感系统的工程设计能力。</td>
      <td>层结构设计</td>
      <td>逐层选择材料、厚度、界面、表面处理和堆叠顺序。</td>
    </tr>
    <tr>
      <td>系统设计</td>
      <td>对器件架构、阵列、封装、信号调理、采集、处理、校准和决策进行端到端设计。</td>
    </tr>
  </tbody>
</table>

## 测评模型配置

| 模型家族 | 当前测评配置覆盖 | 推理配置 |
| --- | --- | --- |
| GPT | GPT-5.2、GPT-5.5、GPT-5.6 Luna、Terra、Sol | `low`、`mid`、`max`、`xhigh` |
| Claude | Sonnet 4.6、Sonnet 5、Opus 4.6、4.7、4.8 | 服务商默认 |
| DeepSeek | V3.1、V3.2、V4 Flash、V4 Pro 0813 | 服务商默认 |
| Qwen | 3.7 Plus/Max/Flash、3.8 Max/Flash | 服务商默认 |
| Kimi | K2.5、K2.6、K2.7 Code、K3 | 服务商默认 |
| GLM | 4.7、5、5.1、5.2 | 服务商默认 |
| MiniMax | M2.1、M2.5 | 服务商默认 |

`evaluation/api/models.yaml` 中每个可运行的 API 配置遵循以下格式：

```yaml
配置名称:
  base_url: https://api.example.com/v1
  api_key_env: PROVIDER_API_KEY
  model: 服务商模型名称
  enable_thinking: false
```

配置名称同时也是结果目录名称。被测模型和 L3 裁判模型可以使用不同配置。

## 项目配置

- Python 3.10 或更高版本
- API 测评需要兼容 OpenAI Chat Completions 的接口
- Agent 流程需要 Codex，并安装仓库中的对应 Skill

## 快速开始

创建隔离环境并安装依赖：

```bash
git clone git@github.com:LMDHQ-0420/TENGBench.git
cd TENGBench
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 生成 QA 基准

先创建本地工作目录，将论文 PDF 放入 `papers/inbox/`，并把 `qa-generation/skills/` 中的三个 Skill 安装或链接到 Codex。编排流程依次执行：

```bash
python qa-generation/scripts/orchestrator/distribute_papers.py
# 在 Codex 中运行 TENGBench-reviewer-writer，处理已分发论文。
python qa-generation/scripts/orchestrator/collect_and_route.py
python qa-generation/scripts/orchestrator/update_master.py
# 如需抽样质检，在 Codex 中运行 TENGBench-qa-validator。
python qa-generation/scripts/orchestrator/assemble_benchmark.py
```

### 运行 API 测评

```bash
cp evaluation/api/models.example.yaml evaluation/api/models.yaml
export OPENAI_API_KEY="your-key"
python evaluation/api/api_test.py
python evaluation/api/run.py --model gpt-example --judge gpt-example
```

只要题集中包含 L3，`--judge` 就是必填参数。程序支持按题断点续跑，结果写入本地 `result/<配置名称>/`。

### 运行 Skill 测评

将 `evaluation/skill/skills/` 中的 Skill 安装到 Codex，先运行 `tengbench-test-orchestrator` 完成答题，再运行 `tengbench-judge-orchestrator` 评审待处理的 L3 答案。两个流程只通过 `evaluation/skill/scripts/` 下的受控读写脚本访问题目和结果。

## 项目结构

```text
TENGBench/
├── asset/                       # README 公开资源
├── qa-generation/
│   ├── scripts/                 # 论文分发、QA 校验、基准组装
│   └── skills/                  # 编排、论文审阅出题、QA 质检 Skill
├── evaluation/
│   ├── api/                     # 并发 API 测评与契约测试
│   └── skill/                   # Codex Skill 测评、受控读写与测试
├── requirements.txt
├── README.md
└── README-ZH.md
```

## 测试

```bash
python -m unittest discover -s evaluation/api/tests
python -m unittest discover -s evaluation/skill/tests
```
