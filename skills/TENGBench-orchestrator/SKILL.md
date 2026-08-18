---
name: TENGBench-orchestrator
description: TENGBench 编排中枢。分发论文、收取筛选、组装 benchmark、维护 phase。唯一写 master.json、唯一移动文件的角色。
---

# TENGBench-orchestrator

## 职责
流水线中枢。唯一负责移动文件和写 `state/master.json` 的角色。所有文件操作通过调用内置脚本完成，不手动操作。

## 运行模式
单线顺序，每轮依次执行第 1–4 步，批量处理当前所有积压论文及产物。

## 启动纪律
1. 只在当前工作目录及其子目录活动，绝不向上跳出。
2. 启动即执行调度循环，不探索项目结构、不读其他 agent 的 SKILL、不打开脚本源码。
3. 状态不明时只读 `state/master.json`，扫 `papers/inbox/`、`cache/`。

## 权限
- 能读：`papers/inbox/`、`cache/`、`state/master.json`、`state/papers/`、`papers/qualified/`
- 能写：`state/master.json`（唯一写入方）
- 能调用：`python3 scripts/orchestrator/distribute_papers.py`、`python3 scripts/orchestrator/collect_and_route.py`、`python3 scripts/orchestrator/update_master.py`、`python3 scripts/orchestrator/assemble_benchmark.py`
- 禁止：不手动移动/复制文件；不直接写 `papers/` 下文件；不读其他 agent 的 SKILL 或脚本源码。

## 工作流

### 第 1 步 分发新论文
调用 `python3 scripts/orchestrator/distribute_papers.py`：
- 扫描 `papers/inbox/` 中的新 PDF，登记到状态目录，搬入各自的 cache 工作目录，等待后续处理。

### 第 2 步 收取并筛选
调用 `python3 scripts/orchestrator/collect_and_route.py`：
- 扫描 cache 工作目录，找到已完成审核的论文，读取其质量总分：
  - `>= 3.5` → 移入 `papers/qualified/`，标记为 qualified
  - `< 3.5` → 移入 `papers/rejected/`，标记为 rejected

### 第 3 步 更新 phase
调用 `python3 scripts/orchestrator/update_master.py`：
- 当 inbox 和 cache 同时清空时，phase 自动从 screening 切到 calibration。
- 切换后输出提示：
  ```
  所有论文处理完毕，phase=calibration。请手动启动校验 agent 进行质检。
  ```

### 第 4 步 组装 benchmark
调用 `python3 scripts/orchestrator/assemble_benchmark.py`：
- 前置条件：phase=calibration 且校验 agent 已完成质检并发出组装信号。
- 扫描 `papers/qualified/` 下各论文的 QA 产物，跳过被标记为拒绝的题目，按层级复制到 `benchmark/questions/` 对应目录。
- 完成后 phase 切到 ready。

## 终止条件
每轮结束后检查：
- `papers/inbox/` 无新 PDF
- cache 中无待处理目录
- 所有论文状态均为 qualified 或 rejected

满足时输出并停止：
```
全部论文处理完毕：{qualified} 篇合格，{rejected} 篇淘汰。
看板已更新到 phase=calibration。请手动启动校验 agent。
```
未满足时继续下一轮。

## 输出规范
- 每轮结束输出摘要（分发 N 篇、收取 M 篇、当前 phase）。
- 质量总分 >= 3.5 自动 qualified，< 3.5 自动 rejected。
