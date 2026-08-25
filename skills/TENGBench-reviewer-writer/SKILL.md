---
name: TENGBench-reviewer-writer
description: "TENGBench paper review and question writing. Given one TENG paper PDF, read it once, rename it, build its index, assign a five-dimensional quality score, and generate as many QA items as possible under cache/{paper_id}/."
---

# TENGBench-reviewer-writer

## 1. Responsibilities

You are a TENG-domain expert and benchmark question writer for TENGBench. Given one TENG paper PDF, read it once and complete four tasks: normalize the filename, build the paper index, assign a five-dimensional quality score, and generate as many QA items as possible. Complete the entire task in the same context (read the paper only once to save tokens).

---

## 2. Operating rules

### Startup discipline

1. Work only in the current working directory and its descendants. Write all paths relative to the current directory and never move upward.
2. At startup, scan `cache/` for directories containing a PDF but no `.complete` marker. Do not first explore the project structure, read other agents' SKILL files, or read scripts from other modules.
3. All information you need is in this SKILL; execute directly.
4. All information you need is in this SKILL; do not read external state files or scan other directories.

### Permission boundaries

- **Can read:** `cache/` (scan pending directories), `state/master.json` (read-only phase check)
- **Can write:** `cache/{paper_id}/`, `state/papers/{paper_id}.json`
- **Can call:** `python3 scripts/reviewer_writer/generate_paper_id.py <cache_paper_dir>`; `python3 scripts/reviewer_writer/qa_schema_validator.py <qa_file>`
- **Prohibited:** moving upward from the current directory; reading or running scripts from other modules; touching `papers/inbox`, `papers/qualified`, or `papers/rejected`; writing `state/master.json`; reading other agents' SKILL files or code.

### Multi-agent concurrency

When `cache/` contains multiple pending directories:

- Dispatch one sub-agent per directory (Task tool, `subagent_type=general-purpose`), with a recommended concurrency of 3–5.
- Each sub-agent writes only to its own `cache/{paper_id}/`; they must not interfere with one another.
- Wait for all sub-agents to finish, collect their results, and scan again.
- For a single paper, process it directly without dispatching a sub-agent.

### Termination conditions

- Process in a loop: scan → process → scan again.
- When no PDF is pending, scan again automatically every 20 minutes and output:
  ```
  [reviewer-writer] No papers are currently pending; checking again in 20 minutes. Processed so far: {n} papers.
  ```
- If the `phase` in `state/master.json` has reached `calibration`, stop polling and output:
  ```
  reviewer-writer: All papers have been processed; phase=calibration. Please close the paper review and question-writing agent manually.
  ```

---

## 3. Input and output

| Direction | Path | Description |
|---|---|---|
| Input | `cache/{paper_id}/paper.pdf` | TENG paper waiting for review |
| Output | `cache/{paper_id}/index.json` | Paper index |
| Output | `cache/{paper_id}/score.json` | Five-dimensional score |
| Output | `cache/{paper_id}/qa/{qa_id}.json` | One file per question |
| State update | `state/papers/{paper_id}.json` | score, qa_count, status=`screened` |
| Completion marker | `cache/{paper_id}/.complete` | When present, skip the paper to prevent duplicate processing |

---

## 4. Workflow (execute in order for each paper)

### Step 1: Parse the paper

Use the Read tool to read the PDF directly under `cache/{stem}/` (Claude's native multimodal reading supports text and figures together). **Do not use `pdftotext` and do not create intermediate text files.**

Determine the paper identity: title, complete author list, first affiliation, full journal name, publication year, and DOI.

### Step 2: Build `index.json`

Write the following fields to `cache/{stem}/index.json` (`paper_id` is temporarily empty):

```json
{
  "paper_id": "",
  "title": "...",
  "authors": ["..."],
  "first_affil": "...",
  "venue": "Full journal name",
  "doi": "...",
  "date": "YYYY-MM",
  "subcategory": "aviation|wearable|tactile|chemical|hmi|iot|biomedical|marine|wind|motion|acoustic|robotics|smarttextile|energyharv|space"
}
```

After reading the paper, choose the single best-matching subcategory from the controlled list of 15 scenarios (see Section 5.7).

### Step 3: Generate `paper_id`

After writing `index.json`, run:

```
python3 scripts/reviewer_writer/generate_paper_id.py <current_paper_directory>
```

The tool will:

- automatically construct `paper_id` from the `title`, `venue`, `date`, `authors`, and `subcategory` fields in `index.json`;
- use the format `{subcategory}_{venue_short}{year}_{lastname}_{word1}_{word2}_{word3}`;
- produce an example such as `aviation_NatComm2023_Xu_Triboelectric_Nanogenerator_Stall`;
- write `paper_id` back to `index.json`;
- rename the PDF to `{paper_id}.pdf`;
- rename the directory to `{paper_id}/`;
- print the paper ID for use in subsequent steps.

From this point onward, use the paper ID returned by the tool; do not assemble it manually.

### Step 4: Assign the five-dimensional score

Read the relevant parts of the paper and assign each dimension a score from 1 to 5 with one-sentence reasoning:

| Dimension | Weight | Evidence to read |
|---|---:|---|
| relevance (domain relevance) | 0.25 | Title, abstract, introduction |
| questionability (question-writing potential) | 0.25 | Methods, device, and results sections |
| richness (information richness) | 0.20 | Survey all sections and estimate how many question types are supported |
| novelty | 0.15 | Publication year (2023+ receives a high score) |
| clarity (clarity of presentation) | 0.15 | Whether figures, tables, and device/method descriptions are clear |

```json
{
  "relevance": 5, "questionability": 4, "richness": 4, "novelty": 3, "clarity": 4,
  "total": 4.15,
  "reasons": {
    "relevance": "...", "questionability": "...", "richness": "...",
    "novelty": "...", "clarity": "..."
  }
}
```

> `total` is the weighted average. Be strict rather than generous; only papers with a screening threshold of `>= 3.5` qualify.

### Step 5: Decide which question types the paper supports

Read the paper and determine which question types it can support:

- For every supported type, write as many questions as possible; there is no upper limit.
- **DG1/DG2/DG3 are mandatory and must not be skipped:** DG1 tests the TENG stack itself (material/thickness/interface of every layer); any paper with a physical device can support it. DG2 tests the complete system workflow (device → array → acquisition → decision); for simple structures, shift the focus toward signal processing. DG3 tests 3D modeling; for simple structures, test topological correctness. “The structure is too simple,” “there is no precise cross-sectional figure,” and “the paper focuses on algorithms or the system level” are not valid reasons to skip them. The only permitted skip is a paper that describes no physical device at all (pure theory or pure simulation); record the reason explicitly in the log.

### Step 6: Write the questions

Generate QA items according to the question-writing rules and type definitions in Section 5. Every question must contain `source_excerpt` (a 100–300-word key excerpt from the paper with a source label, used only for traceability and never placed in the question stem).

### Step 7: Write files and update state

- Use the filename format `{layer}_{type}_{subcategory}_{paper_id}_{number}.json`.
  - Example: `L2_RP1_aviation_aviation_NatComm2023_Xu_Triboelectric_Nanogenerator_Stall_001.json`
- Write the files to `cache/{paper_id}/qa/`.
- After all artifacts have been written, create the empty file `cache/{paper_id}/.complete`.
- Update `state/papers/{paper_id}.json` with the score, `qa_count`, and `status="screened"`.

---

## 5. Question-writing rules

### 5.1 Question types

**General rule:** Every type must focus on its own topic, and the answer must land on data—performance values, parameter magnitudes, fold changes, or range judgments. Purely qualitative descriptions are not acceptable as answers or scoring evidence.

#### L1 Basic layer (BK, not tied to a paper scenario)

Choose the subcategory for each BK question from the candidate subcategories associated with that type:

| Type | Topic | Candidate subcategories |
|---|---|---|
| BK1 Basic theory | Mechanisms and boundary conditions of contact electrification, electrostatic induction, and displacement current | `triboelectric_mechanism` / `electrostatic_induction` / `displacement_current` |
| BK2 Operating modes | Applicable conditions and performance boundaries of the four operating modes | `contact_separation` / `sliding` / `single_electrode` / `freestanding` |
| BK3 Material polarity | Triboelectric series and the effects of surface-modification processes | `triboelectric_series` / `surface_modification` |
| BK4 Performance metrics | Coupling relationships and engineering trade-offs among Voc / Isc / Qsc / Pmax | `output_coupling` / `impedance_matching` |

#### L2 Reasoning layer (RP, tied to a paper scenario)

| Type | Topic |
|---|---|
| RP1 Material-based performance | Effect of material replacement or dopant-ratio changes on performance |
| RP2 Structure-based performance | Effect of geometric parameters, layer count, or array specifications on performance |
| RP3 Scenario-based performance | Effect of excitation conditions or environmental parameters on performance |
| RP4 Long reasoning | Given multiple comparative experimental values, draw a conclusion through multi-step reasoning |

RP1/RP2/RP3 are pure multiple-choice questions (do not attach reasoning steps). RP4 must include `multi_step_reasoning`.

#### L3 Design layer (DG, open-ended answers)

| Type | Topic |
|---|---|
| DG1 TENG layer design | Only the TENG stack itself: materials, thicknesses, interfaces, and stacking order of each functional layer |
| DG2 Complete sensing-system design | A complete workflow covering device structure, array/packaging integration, signal conditioning/acquisition, and signal processing/decision |
| DG3 3D structural modeling | Generate a CAD model from complete geometric parameters |

### 5.2 Question-writing principles

**Principle 1: Questions must be self-contained; do not use paper-specific terminology**

When answering, the evaluated model may rely only on its own knowledge and the question text. It cannot see the paper, `source_excerpt`, or other questions from the same paper. Therefore:

- Never use paper-invented terminology in `question`, `options`, `rubric`, or `required_parts`, including paper-created abbreviations, custom labels, and internal names. Such terms are unseen by the model and invalidate the question.
- Every question stem must independently state all scenario information needed for that question. Do not omit information with references such as “the above scenario,” “as described earlier,” or “this unit.” Even if one paper produces ten RP questions, each stem must restate its own scenario.
- The paper provides scenario and numerical material, not terminology. Translate the paper into general language that a model can understand from its own knowledge: use “a modified silk-protein triboelectric layer” instead of a paper abbreviation and “triboelectric signal” instead of an internal label.
- The stem may use only standard domain terms (contact electrification, electrostatic induction, contact-separation mode, PTFE/PDMS/nylon/silk fibroin, piezoelectric effect, angle of attack/stall/boundary-layer separation, wind speed, etc.) and scenario descriptions explicitly defined in the stem.
- If an L2/L3 question must be scenario-bound, first introduce the required scenario and measured quantity in general language, then ask the question.

**Principle 2: Question information must be neutral and must not reveal the reasoning path**

The stem presents scenario parameters and observed phenomena, but does not provide general knowledge, formulas, or mechanism explanations. The evaluated model must complete all reasoning independently.

- Give constraints only as numerical boundaries; do not attach material properties or mechanism descriptions, because those descriptions reveal the answer direction.
- Do not use leading wording such as “to improve sensitivity” or “because of boundary-layer separation.” State only what happened, not why.
- RP4 options present only a numerical conclusion or conclusion judgment, without explanatory reasons.
- DG questions provide no reference solution, comparison data, or design-direction hints. Rubric deductions should target common incorrect reasoning paths, not merely missing bonus points.

**Principle 3: For every L1/L2 multiple-choice question, the answer must be a specific number**

This is a core constraint. Rewrite any question that fails it.

1. **All five options must be specific values, not prose.** Options may not contain mode names, mechanism explanations, or design descriptions. All five must be in the same order of magnitude, with adjacent values roughly 1.5–2× apart. Do not use ranges such as “2–6 V”; each option must be one exact value.
2. **All numerical values must come from the paper.** The stem parameters, option values, and correct answer must trace to measured values or geometric/material parameters stated by the paper. Standard physical constants (ε₀, elastic modulus, etc.) may be cited directly, but device-level values (voltage, mass, dimensions, accuracy, etc.) must come from the paper and may not be estimated from general knowledge or invented.
3. **The correct answer must be a concrete quantity independently verifiable by calculation.** Summarize the question in one sentence; it must end with “what is the value?” rather than “which one?” or “why?” Choosing the correct option must mean calculating correctly or using the correct formula, not merely selecting a different qualitative direction.

**Principle 4: The correct answer must be counterintuitive, all distractors must be technically plausible, and perform three checks after writing**

**Counterintuitive answer:** Before writing, ask: “Which value would general knowledge suggest?” Make that value a distractor. The correct answer must be superficially counterintuitive and must be the value calculated under the paper's specific constraints. If general knowledge directly points to the correct answer, the question is invalid and must be reconstructed.

**Distractor quality:** Every distractor must correspond to a real calculation error—misusing a formula, dropping a coefficient, making a unit-conversion error, or misreading a paper value—not an invented number. Use neutral wording for all options; do not disparage or evaluate any option. Error types must be diverse rather than five versions of the same mistake.

**Three post-writing checks (all must pass; otherwise rewrite):**

1. Hide the correct answer and inspect the four distractors one by one. Each must look like it could be correct.
2. The five options must have consistent magnitude, with adjacent values 1.5–2× apart.
3. Without reading the paper, can general knowledge immediately eliminate more than one option? If yes, rewrite.

### 5.3 Option requirements

- Every multiple-choice question (BK / RP1 / RP2 / RP3 / RP4) must have **five options (A/B/C/D/E)**, giving a 20% random-guess rate.
- Options should have similar length and symmetric structure, with neutral wording throughout.
- Self-check: hide the answer and inspect each option independently. Each must look potentially correct; if general knowledge can eliminate more than one without the paper, rewrite.

### 5.4 Type-specific writing requirements

**RP4 long reasoning:** Provide complete numerical values from multiple comparative experiments in the paper. The five options must present conclusions only, without reasons. The correct answer is the one that explains all numerical differences at once. Every step in `multi_step_reasoning` must cite concrete values from the stem; include at least four steps.

**DG1 TENG layer design:** **Test only the TENG stack itself; do not cover arrays, systems, or signal processing.** Give application and environmental constraints in the stem (temperature, humidity, excitation magnitude, and target output magnitude, all numerical), then require layer-by-layer design: triboelectric-layer material and thickness, back-electrode material and thickness, substrate/flexible substrate, surface-modification process, interlayer interface (source of the air gap and bonding method), and stacking order. Each scoring point must specify a layer's material, thickness, and selection rationale. Array layout, packaging integration, and signal-processing content must not appear in DG1; those belong to DG2. Every rubric point must require a numerical estimate consistent with the constraints; purely qualitative answers receive no credit. Attach a rubric with 5–6 weighted points.

**DG2 complete sensing-system design:** **Test the complete workflow from device structure to signal decision.** Use one of two data-completeness tracks, selected after assessing the paper:

**Data-rich track** (the paper provides device-level values such as layer thicknesses, area, electrical outputs, and sampling rate): provide the application scenario, engineering constraints, and existing device parameters, then require a complete sensing system covering four stages: (1) device structure (core-layer geometry and connections); (2) array/packaging integration (unit layout, channel partitioning, environmental protection, and fit to the measured object); (3) signal conditioning and acquisition (amplification/filtering/rectification, sampling rate, ADC bit depth, and wired/wireless transmission); (4) signal processing and decision (feature extraction, thresholds/classification, and calibration). Divide the rubric into these four stages; each point must require a numerical estimate consistent with the constraints, such as sampling rate ≥ 2× the Nyquist frequency, channel count equal to the number of array units, and thresholds inferred from measured paper data.

**Data-sparse track** (the paper lacks device-level numbers but describes a structural topology: component composition, groove/air-channel shape, electrode count, array layout, and relative positions): provide the application scenario, performance targets taken from paper measurements (output power, response threshold, positioning accuracy, etc.), and a textual description of the topology (**without dimensions**). Require the evaluated model to do three things: (1) **topology design**—specify every structural decision (groove location, air-channel shape, number of disk electrodes, array layout); (2) **itemized justification**—map every structural feature to a performance target; (3) **reverse validation**—explain what happens if a feature is removed or changed, demonstrating why it is necessary. Each rubric point corresponds to one structural feature. Judge whether the topology agrees with the paper and whether the causal argument is valid; numerical values are not required.

**Mixed case:** Judge data-rich stages for numerical consistency and data-sparse stages for topology reasoning. **This is mandatory and must not be skipped:** “The paper does not give micrometer-scale thicknesses” is precisely why the data-sparse track exists, not a reason to skip. Attach a rubric with 6–8 points.

**DG3 3D structural modeling:** First read structural figures in the PDF (cross-sections, exploded views, SEM images, and schematics) to obtain geometry. If figures lack sufficient geometric parameters, extract as much textual structural information and performance data as possible from the paper (material names, stacking order, qualitative dimensions, fabrication parameters, etc.) to complete the stem. **This is mandatory and must not be skipped:** “There is no exploded view,” “assembly details are missing,” and “parameters remain at the principle level” are not reasons to skip it. Choose between two modes based on the completeness of the paper's geometric information:

**Mode 1: Fully parameterized modeling** (the paper provides precise dimensions and assembly relationships for most listed components): state all functional-layer names, materials, thicknesses, areas/dimensions, stacking order, assembly relationships, coordinate system, modeling task, and scenario use. The evaluated model directly builds from the supplied parameters. Score precise geometry; an error greater than 10% on a paper-specified component loses points.

**Mode 2: Self-completing modeling** (the paper provides only partial dimensions and a principle-level structure description—for example, film thickness, cylinder diameter and array pitch, total electrode area, and working air gap, but not assembly details, exact z coordinates, or frame dimensions): this is the capability being tested. **The evaluated model must infer missing dimensions and complete a self-consistent, buildable assembly.** The stem must provide: (1) every dimension available in the paper, unchanged; (2) the component list and principle-level assembly description (which faces oppose each other, what is above what, and what contacts what); (3) working-principle constraints such as “separated-state air gap ≈3 mm” or “total electrode area 100 mm × 100 mm,” with all inferred dimensions consistent with them; and (4) the modeling task and scenario. **Do not provide values estimated by the question writer—leave missing dimensions for the evaluated model to choose.** During scoring, check that inferred values satisfy the paper's constraints (air gap, reasonable total height, no interference). Emphasize component completeness, exact geometry for paper-specified components, reasonable magnitude of model-selected values, and global consistency (no interpenetrating layers, valid assembly relationships, and no conflict with the working principle).

**Mode selection:** If the paper gives at least 70% of component dimensions, use Mode 1. If it gives core dimensions (a computable reference in any direction) but omits assembly details, use Mode 2. If neither applies (the paper has no numerical values at all), use qualitative descriptions plus conventional process parameters clearly labeled as “estimated values.” The only permitted skip is a paper that describes no physical device at all (pure theory or pure simulation); record the reason explicitly in the log.

---

### 5.6 Question examples

> **Important:** These examples are references, not templates. Questions must be based entirely on the specific content, values, and scenario of the paper at hand; do not copy the structure or numbers from an example. The examples demonstrate what a passing question looks like and do not limit the possible directions.

#### BK1 example

> **Why it is good:** All five options are in the nC range, and general knowledge cannot eliminate any of them. The correct answer requires calculating `Q = ε₀·A·Voc/d` (`A = 59.7×22.0 mm²`, `d = 18 μm`, `Voc = 8 V`) to obtain 5.16 nC. Adjacent options differ by about 1.6×, so only the correct calculation reaches the correct option.

**Background:**

In a wing-surface triboelectric sensing unit, a modified silk-protein triboelectric layer (CSFE) fully covers the top surface of a PCB (planar dimensions 59.7 mm × 22.0 mm). The CSFE thickness is 18 μm and it is treated as a uniform dielectric layer (`ε_r = 1`). A 304 stainless-steel foil periodically contacts the CSFE under airflow. At full contact, the measured open-circuit voltage is `Voc = 8 V`; the vacuum permittivity is `ε₀ = 8.85×10⁻¹² F/m`.

**Question:**

At full contact, what is the equivalent transferred charge at the CSFE–steel interface closest to?

A. 2.0 nC
B. 3.3 nC
C. 5.2 nC
D. 8.4 nC
E. 13.5 nC

**Answer:** C

**Calculation:** `C_eq = ε₀·A/d = 8.85×10⁻¹² × (59.7×22.0×10⁻⁶) / 18×10⁻⁶ ≈ 645 pF`; `Q = C_eq·Voc = 645×10⁻¹² × 8 ≈ 5.16 nC`, closest to C (5.2 nC). B corresponds to underestimating `Voc` by about 50%; D corresponds to overestimating it by about 60%; A and E are both off by more than 2×.

#### BK2 example

> **Why it is good:** A flexible steel foil (0.1 mm thick, 22 mm wide, 95 mm free cantilever length) experiences approximately 960 Pa normal dynamic pressure at 40 m/s. The five options give different foil thicknesses. The correct answer requires using bending stiffness `EI ∝ h³` to determine which thickness can produce deflection ≥3 mm (the initial air gap) under 15 Pa dynamic pressure. General knowledge cannot distinguish the driveability of the 0.08/0.10/0.12 mm options.

**Background:**

Design a triboelectric stall-sensing unit on the wing surface of a fixed-wing UAV (20 cm chord). The elastic steel cantilever has a 22 mm fixed-end width, a 95 mm free length, and an initial 3.0 mm air gap supported by a foam spacer. The steel's elastic modulus is 193 GPa. The unit must start reliably at 8 m/s (normal dynamic pressure ≈38 Pa, maximum deflection ≥3 mm) and must not plastically deform at 40 m/s (normal dynamic pressure ≈960 Pa, `σ_max < 515 MPa`). Use `δ_max = FL⁴/(8EI)`, `I = bh³/12`, and `σ_max = 6FL²/(bh²)`.

**Question:**

Which of the five steel-foil thicknesses is the only one satisfying both “drivable at 8 m/s” and “no plastic failure at 40 m/s”?

A. `h = 0.06 mm` (`δ_max@8m/s ≈ 23 mm ≥ 3 mm`; `σ_max@40m/s ≈ 1280 MPa > 515 MPa`)
B. `h = 0.08 mm` (`δ_max@8m/s ≈ 7.3 mm ≥ 3 mm`; `σ_max@40m/s ≈ 720 MPa > 515 MPa`)
C. `h = 0.10 mm` (`δ_max@8m/s ≈ 3.0 mm ≥ 3 mm`; `σ_max@40m/s ≈ 460 MPa < 515 MPa`)
D. `h = 0.12 mm` (`δ_max@8m/s ≈ 1.7 mm < 3 mm`; `σ_max@40m/s ≈ 320 MPa < 515 MPa`)
E. `h = 0.15 mm` (`δ_max@8m/s ≈ 0.7 mm < 3 mm`; `σ_max@40m/s ≈ 205 MPa < 515 MPa`)

**Answer:** C

**Calculation:** For `h=0.10 mm`, `I = 22×(0.1)³/12×10⁻¹² = 1.83×10⁻¹⁵ m⁴`; `F@8m/s = 38×0.095×0.022 = 0.079 N`; `δ = 0.079×0.095⁴/(8×193×10⁹×1.83×10⁻¹⁵) ≈ 3.0 mm`; `F@40m/s = 960×0.095×0.022 = 2.00 N`; `σ_max = 6×2.00×0.095²/(0.022×(0.1×10⁻³)²) ≈ 460 MPa < 515 MPa`. Both constraints are satisfied; this is the only feasible design.

#### BK3 example

> **Why it is good:** All five options are within the μC/m² range. General knowledge may suggest that silk protein is relatively negative, but cannot provide the exact value. The correct answer requires using `σ = ε₀·Voc/d` (`d = 18 μm`, `Voc = 8 V`) with the CSFE thickness and open-circuit voltage from the paper to calculate 3.93 μC/m². Adjacent options differ by about 1.6×, so one calculation error reaches a neighboring distractor.

**Background:**

A research group modifies natural silk fibroin (SF) with 15 wt% polyurethane (WPU) to create a modified composite film (CSFE). The film is 18 μm thick, and its dielectric constant is conservatively taken as `ε_r = 1`. CSFE is paired with a 304 stainless-steel foil; at full contact, the open-circuit voltage is `Voc = 8 V`. The vacuum permittivity is `ε₀ = 8.85×10⁻¹² F/m`.

**Question:**

What is the equivalent surface charge density at the CSFE–304 stainless-steel interface closest to?

A. 1.5 μC/m²
B. 2.5 μC/m²
C. 3.9 μC/m²
D. 6.3 μC/m²
E. 10.1 μC/m²

**Answer:** C

**Calculation:** `σ = ε₀·Voc/d = 8.85×10⁻¹² × 8 / 18×10⁻⁶ = 3.93 μC/m²`, closest to C (3.9 μC/m²). B corresponds to underestimating `Voc` by about 55% (approximately a 5 V level); D corresponds to overestimating it by about 60% (approximately a 13 V level); A and E are both off by more than 2×.

#### BK4 example

> **Why it is good:** All five options are in the nW range. General knowledge indicates that TENG power is low but cannot distinguish whether 8/40/160 nW is correct. The correct answer requires calculating `R_eq = Voc/Isc = 400 MΩ` and then `Pmax = Voc²/(4R_eq) = 40 nW`. A common error is to use `Voc×Isc = 160 nW` and omit the 1/4 matched-load transfer factor, leading to E.

**Background:**

A wing-surface triboelectric sensing unit measures `Voc = 8 V` and `Isc = 20 nA` at a wind speed of 20 m/s. Under a matched load, the maximum output power is `Pmax = Voc²/(4R_eq)`, where `R_eq = Voc/Isc`.

**Question:**

What is the maximum output power `Pmax` under a matched load closest to?

A. 4 nW
B. 16 nW
C. 40 nW
D. 100 nW
E. 160 nW

**Answer:** C

**Calculation:** `R_eq = 8 V / 20×10⁻⁹ A = 400 MΩ`; `Pmax = (8)²/(4×400×10⁶) = 64/1.6×10⁹ = 40×10⁻⁹ W = 40 nW`. E corresponds to directly using `Voc×Isc` without the 1/4 factor; D corresponds to underestimating `R_eq`; B and A correspond to overestimating `R_eq` or `Voc`.

#### RP1 example

> **Why it is good:** All five options are in the V range and adjacent values differ by about 1.6×. The stem gives a wind speed of 40 m/s and a 1000-point STD window. The correct answer requires knowing the paper's Fig. 3b value of approximately 0.25 V for the T-signal STD during normal, unstalled flight. General knowledge may mistake STD for the raw signal amplitude (about 8 V) and select D/E.

**Background:**

A research group deploys a contact-separation triboelectric sensing system on the surface of an NACA0012 airfoil (20 cm chord). A flexible 304 stainless-steel foil (0.1 mm thick) strikes a modified silk-protein triboelectric layer under airflow and outputs a triboelectric signal (T-signal). In a wind-tunnel test at 40 m/s, the system is in a stable, unstalled state (`AoA = 0°`). The T-signal is processed using a standard-deviation (STD) algorithm: one STD value is calculated for every 1000 real-time data points.

**Question:**

At 40 m/s and `AoA = 0°` in a stable, unstalled state, what value is the T-signal STD result closest to?

A. 0.05 V
B. 0.10 V
C. 0.25 V
D. 1.5 V
E. 5.0 V

**Answer:** C

#### RP2 example

> **Why it is good:** All five options are hole-area fractions, with adjacent values differing by about 1.4×. The correct answer requires using `b_eff = b×(1−ρ_hole)` and `EI ∝ b_eff·h³` for the triangularly arranged diamond holes in the paper (covering the first 50 mm and giving an equivalent solid-width fraction of 65%). General knowledge may assume “more holes means more sensitivity” and choose the largest hole fraction.

**Background:**

A research group introduces triangularly arranged diamond-shaped holes (each with 3 mm × 3 mm diagonals) in the first half (`x = 0–50 mm`) of a 304 stainless-steel foil (100 mm long, 22 mm wide, 0.1 mm thick), reducing the effective bending width from 22 mm to `b_eff`. The measured T-signal STD increases from 0.05 V to 0.25 V at 8 m/s after perforation, while the maximum stress at 40 m/s remains below the tensile limit (515 MPa).

**Question:**

What is the area hole fraction (hole area / total area) of this perforation design closest to?

A. 15%
B. 22%
C. 35%
D. 50%
E. 65%

**Answer:** C

**Calculation:** The paper gives an equivalent solid-width fraction `b_eff/b = 0.65`, so the hole fraction is `1 − 0.65 = 35%`, corresponding to C. A/B provide insufficient perforation and limited stiffness reduction, leaving insufficient deflection at 8 m/s; D/E provide excessive perforation and cause stress to exceed the tensile limit at 40 m/s.

#### RP3 example

> **Why it is good:** All five options are in the V range and adjacent values differ by about 1.6×. The stem states that the stalled T-signal falls below 0.3 V, which may anchor a model to A/B by underestimating the P-signal. The correct answer C requires knowing the typical output level of the PVDF excited by reversed flow in full stall (about 2 V measured in Fig. 3d), which general knowledge cannot distinguish from B.

**Background:**

A research group deploys a triboelectric stall-sensing system on an NACA0012 airfoil (20 cm chord) and tests it in a wind tunnel at 40 m/s. Above 16° AoA, the T-signal amplitude falls to the noise floor (<0.3 V), while the P-signal appears and continues to increase. The PVDF piezoelectric film has an area of 20.3 mm × 10.0 mm and is installed on the rear chordwise section of the steel foil.

**Question:**

At 40 m/s and `AoA = 18°` (fully stalled), what is the P-signal open-circuit voltage peak closest to?

A. 0.3 V
B. 0.8 V
C. 2.0 V
D. 5.0 V
E. 12.0 V

**Answer:** C

#### RP4 example

> **Why it is good:** The four accuracies form a 2×2 factorial design. The correct answer requires identifying fixed P-signal processing as the control variable, reading two differences (18 pp and 12 pp), and averaging them to obtain 15 pp. General knowledge may directly use M1−M2 = 26 pp without controlling for the P-signal difference, or compare only M1−M4 = 18 pp; these errors map to D and E.

**Background:**

A research group deploys a coupled triboelectric–piezoelectric stall-sensing system on an NACA0012 airfoil (20 cm chord). After calibration in a wind tunnel with turbulence intensity <0.2% and wind speed 40 m/s, the system is tested in flight at turbulence intensity >1%. The researchers compare four signal-processing schemes over 100 independent stall tests:

| Scheme | T-signal processing | P-signal processing | Accuracy |
|------|--------------|--------------|--------|
| M1 | STD | Prominence | 97% |
| M2 | Prominence | STD | 71% |
| M3 | STD | STD | 83% |
| M4 | Prominence | Prominence | 79% |

**Question:**

Using the four values above, while holding the P-signal algorithm constant, what is the best estimate of the accuracy improvement (percentage points) from switching the T-signal algorithm from Prominence to STD?

A. 5 pp
B. 10 pp
C. 15 pp
D. 21 pp
E. 26 pp

**Answer:** C

**Reasoning chain:**

1. To estimate the independent contribution of the T-signal algorithm (STD vs. Prominence), hold the P-signal algorithm fixed and read the difference under both conditions.
2. Hold `P=Prominence`: M1 (`T=STD`) = 97%, M4 (`T=Prominence`) = 79%, difference = **18 pp**.
3. Hold `P=STD`: M3 (`T=STD`) = 83%, M2 (`T=Prominence`) = 71%, difference = **12 pp**.
4. The differences are not equal (18 ≠ 12), indicating a T×P interaction; the controlled best estimate is `(18 + 12) / 2 = **15 pp**`.
5. E (26 pp) directly uses M1−M2 without holding P-signal constant; D (21 pp) incorrectly increases 18 pp; B reads only the 12 pp under `P=STD` and decreases it.

#### DG1 example

> **Why it is good:** This question tests only the stack itself—material and thickness selection for the substrate, triboelectric layer, back electrode, surface treatment, and air-gap interface—and does not involve arrays or signal processing. The −40°C and high-humidity constraints make the obvious choice of PTFE (strongly negative polarity) fail because electrostatic adhesion suppresses impacts. The correct answer must choose a positive-polarity organic layer and justify the dopant ratio. Every layer thickness must be checked against the total-thickness limit of 0.5 mm.

**Background:**

Design the **TENG stack itself** for an airflow-driven contact-separation TENG on an aircraft surface operating from −40°C to 85°C at up to 95% relative humidity. The opposing elastic metal foil is fixed (0.1 mm thick 304 stainless steel); design the mating stack. The target output is `Voc = 8 V` at full contact.

**Constraints (stack only):**

- Total stack thickness from the bottom of the substrate to the triboelectric surface ≤ 0.5 mm.
- The triboelectric surface must be **positive-polarity** relative to the metal foil to avoid impact suppression by electrostatic adhesion at high humidity and low temperature.
- No brittle fracture at −40°C (fracture strain >5%).
- Give a material, numerical thickness, and one-sentence reason for every layer.

**Question:**

Design the stack layer by layer, covering:

1. Substrate: material and thickness (flexible substrate that tolerates bending at −40°C).
2. Back electrode: material and thickness (conductive layer deposited on the substrate).
3. Triboelectric layer: material and thickness (positive polarity and good low-temperature toughness); if modified, give the dopant ratio.
4. Surface treatment: microstructure type and feature size (to increase effective contact area).
5. Air-gap interface: source and value of the natural gap between the triboelectric surface and metal foil at rest.
6. Stack-order diagram (written description from bottom to top).

**Scoring rubric (total 1.0):**

| Dimension | Weight | Scoring points |
|------|------|----------|
| Substrate selection | 0.15 | Select PI (−269 to 400°C range) or PET and give a 25–125 μm thickness; if selecting PDMS, explain the embrittlement risk near its glass-transition temperature at −40°C; purely qualitative answers receive no credit. |
| Back electrode | 0.15 | Select Cu/Ag/ITO with a thickness of 50 nm–3 μm; state the deposition method (magnetron sputtering or evaporation) and sheet-resistance order (<10 Ω/sq); identify ITO brittleness if used. |
| Triboelectric material and doping | 0.25 | Select a positive-polarity material (silk protein/nylon/cellulose); if selecting silk protein, give 15 wt% WPU doping and explain the β-sheet strengthening mechanism and low-temperature toughness; PTFE/FEP (negative polarity) receives 0 because it violates the polarity constraint. |
| Surface treatment | 0.20 | Give a microstructure type (microcolumn array/sandpaper template/plasma etching), feature size in the 1–50 μm range, and an estimated contact-area increase of at least 2×; no numerical size receives no credit. |
| Air gap and thickness calculation | 0.25 | Give the gap source (surface feature height or pre-bending) and a numerical value (10–100 μm); sum all layer thicknesses to ≤0.5 mm and show the calculation; if too thick, adjust and recalculate. |

#### DG2 example (data-rich track)

> **Why it is good:** It covers the full “device connection → array integration → conditioning/acquisition → processing/decision” chain, and every missing stage loses points. A general answer tends to discuss only device structure and omit the Nyquist calculation and latency-budget decomposition. The sampling rate must satisfy ≥2×40 Hz = 80 Hz (the paper uses 1 kHz, 25× oversampling), and the latency budget must close at ≤500 ms after breaking it down by stage. At 1 kHz, a 1000-point STD window is exactly 1 s, so its temporal resolution must be reconciled with the 150 ms wireless delay; this is a non-general contribution from the paper. **This is the data-rich track.**

**Background:**

A research group deploys an airborne stall-warning sensing system on a fixed-wing UAV (1420 mm wingspan, 7.9 m/s cruise speed, total mass 1810 g). The existing sensing unit consists of a suspended steel foil (0.1 mm thick), a modified silk-protein triboelectric layer, and an integrated rear PVDF section. Single-unit wind-tunnel calibration gives: unstalled T-signal STD ≈0.25 V, stalled T-signal drops to the noise floor (<0.3 V), P-signal peak rises to ≈2 V, and the main foil-impact frequency is approximately 40 Hz.

**Constraints:**

- Total system mass ≤10 g, including sensor units and acquisition circuitry.
- One sensing unit per wing, two units total and four signal channels (`T×2 + P×2`).
- End-to-end wireless warning latency ≤500 ms.
- Warning accuracy ≥95% over 100 independent stall tests.

**Question:**

Design the complete sensing system and give a quantitative plan for each stage:

1. **Device connection:** routing and shielding from every device electrode to the acquisition board for the T/P channels.
2. **Array integration:** installation locations of the two units on the wings (spanwise percentages) and the aerodynamic rationale.
3. **Signal conditioning and acquisition:** amplification and range per channel, sampling rate with a Nyquist calculation, ADC channel count and bit depth, wireless transmission, and a stage-by-stage latency budget.
4. **Signal processing and decision:** algorithm for each T/P channel, threshold values based on calibration data, and joint two-channel decision logic.

**Scoring rubric (total 1.0):**

| Dimension | Weight | Scoring points |
|------|----------|----------|
| Device connection | 0.15 | T channel: differential routing from the steel-foil back electrode and triboelectric-layer back electrode; P channel: independent routing of the upper and lower PVDF silver electrodes; independent shielding for both channels; missing any electrode route loses half of this point. |
| Array position | 0.15 | Spanwise 60–80% (early local-stall region near the wing tip, where the P-signal is stronger); give a percentage and one reason based on spanwise load distribution; “on the wing surface” without a numerical location receives no credit. |
| Sampling-rate calculation | 0.20 | State the Nyquist condition `f_s ≥ 2×40 = 80 Hz` and choose an actual value ≥1 kHz (25× oversampling for stable STD-window statistics); use four ADC channels and ≥12 bits (resolving the 0.3 V threshold at <1/10 of full scale); no numbers receives no credit. |
| Latency budget | 0.20 | Decompose the stages and keep the sum ≤500 ms: acquisition buffer + STD/Prominence computation + wireless transmission (approximately 150 ms measured in the paper) + terminal decision; list numerical values and sum them. |
| Algorithm and thresholds | 0.20 | T channel: STD with a 1000-point window and 1 s resolution, threshold 0.3 V (noise floor); P channel: Prominence isolated-peak detection with a threshold above the approximately 2 V background level; joint logic: T drop + P appearance → stall alarm; thresholds must cite the calibration data in the stem. |
| Accuracy validation | 0.10 | Validate with 100 independent stall tests at ≥95% accuracy; give the maximum missed and false alarms (each ≤5); no validation plan receives no credit. |

#### DG2 example (data-sparse track)

> **Why it is good:** The paper does not provide device-level values such as electrode thickness, substrate material, or interlayer spacing, but it gives the topology (eight PTFE tubes, an Al electrode array, and insole integration) and system performance (charging time and positioning accuracy). The question asks the evaluated model to reverse-design the topology from performance targets and justify every choice—why eight tubes rather than four, how to arrange electrodes for uniform response, and which insole locations produce the strongest signals. Every structural feature must be reverse-validated by stating what happens if it is removed or changed. General knowledge can give only a generic solution and cannot recover the paper's topology details.

**Background:**

A research group develops an insole-based self-powered positioning system. Walking pressure drives triboelectric generation; harvested energy intermittently powers a Bluetooth beacon through a collection circuit for indoor gait-position tracking. The paper provides only the following information:

**Structural topology (no dimensions):** Eight vertical hollow PTFE tubes (outer diameter 8 mm, inner diameter 6 mm, height 15 mm) are arranged inside the insole according to the foot-pressure distribution. Segmented aluminum-foil electrodes are placed at the top and bottom of the tube array. During a step, the tubes deform radially and undergo contact separation with the electrodes.

**Measured performance:** A single step charges the storage capacitor enough to power one Bluetooth broadcast; indoor positioning accuracy is approximately 0.5 m; continuous walking maintains periodic beacon broadcasts.

**Question:**

The paper does not disclose device-level parameters such as electrode thickness, substrate material, or interlayer spacing. Starting from the performance targets above, complete the topology design and justification:

1. **Array topology:** How should the eight tubes be arranged in the insole plane? Draw a distribution diagram and explain the placement logic of each tube. Why eight—what problems would four or sixteen cause?
2. **Electrode configuration:** Why use segmented Al electrodes instead of one continuous sheet? Where should segment boundaries be placed, and how should they correspond to foot-pressure zones?
3. **Deformation mechanism:** Why use hollow tubes instead of solid cylinders or a flat sheet? What advantages does radial-compression contact separation have over axial compression?
4. **Position tracking:** How can foot position be extracted from differences among tube outputs? Which channels must be routed independently?
5. **Reverse validation:** Choose two structural features (for example, the hollow structure and segmented electrodes) and explain which metric (charging rate, positioning accuracy, or broadcast period) would degrade if each feature were removed or changed, and why.

**Scoring rubric (total 1.0):**

| Dimension | Weight | Scoring points |
|------|----------|----------|
| Array topology | 0.25 | Cover high-pressure sole regions, mainly forefoot and heel (for example, 4+4 or 5+3); provide a distribution diagram and placement logic for every tube; justify the eight-tube trade-off (four gives insufficient positioning resolution, sixteen weakens per-tube output and increases cost); missing the count trade-off loses half of this point. |
| Electrode segmentation | 0.20 | Align segments with foot-pressure zones (independent forefoot/midfoot/heel segments); map position to different segment amplitudes; a continuous electrode receives 0 because it cannot localize position. |
| Deformation mechanism | 0.20 | Hollow tubes are easy to compress radially (low stiffness), allow large deformation, and increase contact area during compression; compare with a solid column (too stiff to compress) and a flat sheet (no localized response); no comparison receives no credit. |
| Position tracking | 0.20 | Route at least independent forefoot and heel channels; infer position from inter-channel amplitude ratios; explain the relationship between channel count and positioning resolution; a merged single-channel output cannot localize and loses the full point. |
| Reverse validation | 0.15 | For two features, provide a complete causal chain of “what metric degrades + why,” such as hollow removed → radial stiffness increases → deformation decreases → charge per step decreases → charging rate decreases → broadcast period increases; “it gets worse” without a mechanism receives no credit. |

#### DG3 example

> **Why it is good:** Every value that would otherwise require calculation (the PVDF leading-edge coordinate, each layer's z range, and the overhanging steel length) is supplied, so the task tests modeling rather than calculation. Scoring ignores written descriptions and checks only geometric correctness of the model file. The four unintuitive details most likely to be silently omitted are the Cu electrode on the underside of the steel foil, the rear placement of PVDF, the 45° diamond holes only in the front half, and the 40.3 mm steel overhang beyond the PCB.

**Background:**

A wing-surface stall-sensing unit is installed on the upper surface of an NACA0012 airfoil (200 mm chord). The lower-left corner of the PCB's leading edge is the coordinate origin (`x` chordwise, `y` spanwise, `z` normal to the wing). Complete component geometry:

**1. PCB substrate**

- `x = 0–59.7 mm`, `y = 0–22.0 mm`, `z = 0–1.6 mm`
- Material: FR4 (`ρ = 1900 kg/m³`)

**2. Modified silk-protein triboelectric layer**

- `x = 0–59.7 mm`, `y = 0–22.0 mm`, `z = 1.600–1.618 mm` (18 μm thick)

**3. PVDF piezoelectric film**

- `x = 39.4–59.7 mm`, `y = 6.0–16.0 mm`, `z = 1.618–1.728 mm` (110 μm thick)
- One-micrometer silver electrodes on both faces are included in this thickness; polarization is along the z axis.

**4. Foam spacer**

- `x = 0–5.0 mm`, `y = 0–22.0 mm`, `z = 1.618–4.618 mm` (3.0 mm high)

**5. 304 stainless-steel suspended foil**

- Overall size: `x = 0–100.0 mm`, `y = 0–22.0 mm`, `z = 4.618–4.718 mm` (0.1 mm thick)
- `x = 0–5.0 mm`: fixed end supported by the spacer; `x = 5.0–100.0 mm`: freely suspended.
- `x = 59.7–100.0 mm` (40.3 mm long): fully overhangs the PCB.
- **Copper back electrode:** covers the **underside** of the steel foil (the `z = 4.618 mm` face), 3 μm thick (`z = 4.615–4.618 mm`), with no copper inside the holes.
- **Perforated region:** `x = 0–50.0 mm`; squares rotated by 45° (diamonds), with 3.0 mm × 3.0 mm diagonals.
  - Odd columns: hole centers `x = 5.0, 12.5, 20.0, 27.5, 35.0, 42.5 mm`; `y = 3.0, 8.5, 14.0, 19.5 mm`.
  - Even columns: hole centers `x = 8.75, 16.25, 23.75, 31.25, 38.75, 46.25 mm`; `y = 5.75, 11.25, 16.75 mm`.
  - Hole edges are at least 2.0 mm from the outer steel profile.
- **Solid region:** `x = 50.0–100.0 mm`, with no holes.

**Task:**

Use a 3D modeling tool (FreeCAD / SolidWorks / Fusion 360 / OpenSCAD, etc.) to generate the complete assembly and output a model file or a complete executable modeling script. It must satisfy:

1. All five components are independent solids with exactly the coordinates and parameters above.
2. The front half of the steel foil (`x = 0–50 mm`) contains the complete hole array; holes are 45°-rotated diamonds, and odd/even column y coordinates follow the stated offset pattern.
3. The copper back electrode is an independent thin layer attached to the underside of the steel foil, with no copper in the holes.
4. Output an xz section (`y = 11 mm`) in which every layer is visible and thickness magnitudes are correct.
5. Output an xy top view of the steel foil in which the perforated/solid boundary at `x = 50 mm` is clear.

**Scoring rubric (total 1.0):**

| Dimension | Weight | Scoring points |
|------|----------|----------|
| Component completeness | 0.25 | All five components are independent solids; the Cu electrode is a separate 3 μm layer on the steel underside rather than fused to the steel; PVDF starts at `z = 1.618 mm`, flush with the CSFE top surface. |
| Assembly correctness | 0.25 | The steel section `x = 59.7–100.0 mm` is suspended with no support solid; PVDF starts at `x = 39.4 mm`; spacer `z = 1.618–4.618 mm`; steel bottom `z = 4.618 mm` aligns with the spacer top. |
| Perforation-array geometry | 0.30 | Holes are diamonds (45° rotated), not squares; odd/even column y coordinates are offset in a triangular stagger rather than a right-angle grid; holes exist only for `x < 50 mm`; the region `x > 50 mm` is solid; hole edge clearance is ≥2 mm. |
| Section view | 0.10 | The xz section shows micrometer-scale films (CSFE 18 μm, Cu 3 μm) together with the millimeter-scale substrate; the air gap at `x = 5 mm` is approximately 3 mm. |
| Top view | 0.10 | The perforated/solid boundary at `x = 50 mm` is clear, and the PVDF outline (`x = 39.4–59.7 mm`, `y = 6–16 mm`) is identifiable. |

---

### 5.7 Controlled `subcategory` list

`subcategory` is controlled: choose the best-matching one of the 15 sensing scenarios for L2/L3, and choose the candidate subcategory associated with the question type for L1.

| Scenario | Description |
|---|---|
| aviation | Aerospace: stall/turbulence/wind speed/rotational speed/structural health |
| wearable | Wearable health: pulse/respiration/gait/heart rate |
| tactile | Tactile sensing and electronic skin: pressure/touch/force |
| chemical | Chemical and biosensing: ions/humidity/gas/liquid–solid interfaces |
| hmi | Human–machine interaction: gestures/touch/smart surfaces |
| iot | IoT and smart infrastructure: transportation/industry/buildings |
| biomedical | Implantable sensing and medical diagnosis: in-body sensing/POCT |
| marine | Marine and blue-energy sensing: water flow/waves/corrosion |
| wind | Wind energy and environmental monitoring: wind speed/wind direction/weather |
| motion | Motion and posture recognition: limbs/gait/motion capture |
| acoustic | Acoustic and vibration sensing: sound/noise/mechanical vibration |
| robotics | Robotics and dexterous manipulation: robotic arms/grippers/posture |
| smarttextile | Smart textiles and clothing: textile sensing/interactive garments |
| energyharv | Self-powered energy-harvesting monitoring: device state/power awareness |
| space | Space and extreme environments: space debris/radiation/extreme temperature and pressure |

For each paper, generate as many questions as possible for every question type the paper supports; there is no fixed quota.

### 5.8 L1 question-writing rules (on demand)

1. After reading the paper, determine whether it is especially relevant to a BK subcategory (for example, a detailed discussion of contact electrification supports BK1/`triboelectric_mechanism`, while comparisons of multiple operating modes support BK2/`sliding`, etc.).
2. If it matches, write questions; if not, skip it. Do not force questions merely to fill a quota.
3. Use diverse angles and avoid repeating the same angle within one subcategory.

---

## 6. QA JSON schema

After writing, self-check with `python3 scripts/reviewer_writer/qa_schema_validator.py <qa_file>` and repair any failure.

### Common fields (all question types)

```json
{
  "qa_id": "L1_BK1_triboelectric_mechanism_Xu2023_NatComm_stall_001",
  "type": "RP1",
  "layer": "L2",
  "subcategory": "aviation",
  "source_paper_id": "Xu2023_NatComm_stall",
  "source_excerpt": "Key passage from the paper… (Source: Section 3, Fig. 4)",
  "question": "Question stem…",
  "scoring": {"mechanism": "A"},
  "multi_step_reasoning": null
}
```

> `qa_id` must match the filename and use `{layer}_{type}_{subcategory}_{paper_id}_{number}`. For L1, `subcategory` is the type-specific subcategory (such as `triboelectric_mechanism`); for L2/L3, it is a sensing scenario (such as `aviation`).

### Type-specific fields

**BK / RP1 / RP2 / RP3 (pure multiple choice, 5 options)**

```json
"options": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."},
"answer": "C",
"scoring": {"mechanism": "A"}
```

**RP4 (long reasoning, 5 options, reasoning steps required)**

```json
"options": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."},
"answer": "C",
"multi_step_reasoning": ["Step 1 (cite concrete values)…", "Step 2…", "Step 3…", "Step 4…"],
"scoring": {"mechanism": "A"}
```

**DG1 / DG2 (open-ended short answer)**

```json
"rubric": [{"key": "contains triboelectric layer", "weight": 0.2}, ...],
"reference_answer": "…",
"multi_step_reasoning": ["Step 1…", ...],
"scoring": {"mechanism": "A+B", "rubric_keys": [...]}
```

**DG3 (CAD modeling)**

```json
"required_parts": [...],
"scenario_checklist": [...],
"target_dimensions": {...},
"scoring_detail": {
  "execution": "Execution scoring rule…",
  "structure": "Required-component completeness rule…",
  "scenario": "Scenario-fit scoring rule…",
  "geometry": "Geometric-magnitude scoring rule…",
  "efficiency": "Efficiency-threshold scoring rule…"
},
"scoring": {
  "mechanism": "A+B",
  "execution": 0.25, "structure": 0.35, "scenario": 0.20,
  "geometry": 0.10, "efficiency": 0.10
}
```

> `multi_step_reasoning` is required only for RP4 / DG1 / DG2. Leave it `null` for BK / RP1 / RP2 / RP3.

---

## 7. Output requirements

- Process each paper independently and write to its own `cache/{paper_id}/`; do not interfere with other papers.
- Do not invent information absent from the paper. Every `source_excerpt` must genuinely come from that paper.
- Every question must include a `source_excerpt` (100–300 words plus the source location), used only for traceability and never inserted into the question stem.
- Output must strictly conform to the schema. After writing, run `python3 scripts/reviewer_writer/qa_schema_validator.py <qa_file>` and repair any failure.
