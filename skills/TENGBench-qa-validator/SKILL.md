---
name: TENGBench-qa-validator
description: TENGBench 校验。在 phase=calibration 触发：题目抽检，打标记通知 orchestrator 组装 benchmark。
---

# TENGBench-qa-validator

## 职责
构建期质量把关（calibration 阶段）。人工抽检题目质量，用标记文件通知下游组装 benchmark。不移动任何文件，只打标记。

## 运行模式
按题型分派子 agent 并发抽检（Task 工具），等所有子 agent 完成后单线写根目录完成标记。

## 启动纪律
1. 只在当前工作目录及其子目录活动，绝不向上跳出。
2. 启动即检查 `state/master.json` 的 phase 是否 = calibration，不是则报告"未到校验阶段"并退出。
3. 不探索项目结构、不读其他 agent 的 SKILL/脚本。

## 权限
- 能读：`papers/qualified/*/*/qa/*.json`、`state/master.json`
- 能写：`papers/qualified/` 下的通过/剔除标记文件
- 禁止：不调用任何脚本；不移动/删除任何文件；不写 `state/master.json`；不读其他模块脚本。

## 工作流

### 第 1 步 题目抽检（人工辅助）
从各题型各抽 5–10%（glob `papers/qualified/*/*/qa/*.json`），核对：
- 题干有无歧义或错误
- 选择题正确答案合理，干扰项在其他场景下成立
- DG 题 rubric 每个得分点数值化、可判（纯定性描述须修正）
- source_excerpt 真实来自该论文且出处准确

对每道被抽到的题，在同目录写标记文件：
- 通过（含修复后通过）：对通过的题打通过标记
- 不可修复：对不可修复的题打剔除标记
- 未被抽到的题：不写标记，下游组装时默认通过

### 第 2 步 完成通知
所有抽检标记写完后，在题库根目录写完成标记，通知下游可以组装 benchmark。

## 终止条件
- 抽检标记全部写完。
- 完成标记已写入。
- 输出："校验完成，完成标记已写入，等待下游组装 benchmark。"

## 输出规范
- DG 题 rubric 纯定性得分点须修正后再打通过标记。
