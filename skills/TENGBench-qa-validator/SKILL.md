---
name: TENGBench-qa-validator
description: TENGBench 校验。在 phase=calibration 触发：题目抽检，打标记通知 orchestrator 组装 benchmark。
---

# TENGBench-qa-validator

## 职责
构建期质量把关（calibration 阶段）。人工抽检题目质量，用标记文件通知 orchestrator 组装 benchmark。不移动任何文件，只打标记。

## 运行模式
按题型分派子 agent 并发抽检（Task 工具），等所有子 agent 完成后单线写根目录 `.validated`。

## 启动纪律
1. 只在当前工作目录及其子目录活动，绝不向上跳出。
2. 启动即检查 `state/master.json` 的 phase 是否 = calibration，不是则报告"未到校验阶段"并退出。
3. 不探索项目结构、不读其他 agent 的 SKILL/脚本。

## 权限
- 能读：`papers/qualified/*/*/qa/*.json`、`state/master.json`
- 能写：`papers/qualified/` 下的 `.validated`/`.rejected` 标记文件
- 禁止：不调用任何脚本；不移动/删除任何文件；不写 `state/master.json`；不读 scripts/orchestrator。

## 工作流

### 第 1 步 题目抽检（人工辅助）
从各题型各抽 5–10%（glob `papers/qualified/*/*/qa/*.json`），核对：
- 题干有无歧义或错误
- 选择题正确答案合理，干扰项在其他场景下成立
- DG 题 rubric 每个得分点数值化、可判（纯定性描述须修正）
- source_excerpt 真实来自该论文且出处准确

对每道被抽到的题，在同目录写标记文件：
- 通过（含修复后通过）：写同名 `.validated`（如 `L2_RP1_aviation_Xu2023_NatComm_stall_001.validated`）
- 不可修复：写同名 `.rejected`
- 未被抽到的题：不写标记，orchestrator 组装时默认通过

### 第 2 步 完成通知
所有抽检标记写完后，在 `papers/qualified/` 根目录写空文件 `.validated`，通知 orchestrator 可以运行 `assemble_benchmark.py`。

## 终止条件
- 抽检标记全部写完。
- `papers/qualified/.validated` 已创建。
- 输出："校验完成，papers/qualified/.validated 已创建，等待 orchestrator 组装 benchmark。"

## 输出规范
- DG 题 rubric 纯定性得分点须修正后再打 `.validated`。
- 所有操作日志输出到 `logs/qa_validator/{date}.log`。
