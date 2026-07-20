# Seven-model, seven-case closed-loop benchmark

This is the latest **fully comparable** internal model run available at submission time: seven model routes were evaluated on the same seven strict, text-only Gold cases through 49 independent, turn-by-turn chat sessions. Each route received 66 canonical calls, for 462 canonical calls in total. Model-triggered correction and clarification calls remained part of the stability and efficiency assessment.

The private strict-text corpus now contains nine cases, but the two newest cases were added after this benchmark. They were not rerun across all seven routes, so the results below are reported honestly as a **seven-case benchmark**, not a nine-case benchmark.

## Overall results

| Rank | Model route | Actual model | Effort | Average /100 | Seven-case total /700 | Range | Extra correction or clarification calls | Sanitized practitioner assessment |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | Sol Medium | `gpt-5.6-sol` | medium | **91.43** | 640 | 87–95 | 5 | Most stable overall. Strongest at preserving evidence boundaries, separating retest results from mechanism, and revising long cases without reviving discarded claims. Human review is still required. |
| 2 | Terra Medium | `gpt-5.6-terra` | medium | **88.57** | 620 | 85–92 | 2 | Strong and consistent. Practically tied with Luna Medium at this benchmark's resolution; occasionally used slightly more assertive language than the evidence supported. |
| 3 | Luna Medium | `gpt-5.6-luna` | medium | **88.43** | 619 | 78–93 | 3 | Strong, concise, and source-faithful. Asked fewer proactive questions in some cases and made one difficult long-context attribution error that was corrected. |
| 4 | Luna XHigh | `gpt-5.6-luna` | xhigh | **86.14** | 603 | 75–93 | 6 | Strong on short and medium cases, but heavier output and more identity, ordering, and safety-boundary errors in the longest case than Luna Medium. |
| 5 | Kimi K3 | `kimi-k3` | max | **68.29** | 478 | 58–78 | 19 | Usually found the main thread and asked broad questions, but more often invented fixed doses or follow-up schedules and overcommitted to mechanisms. Required intensive supervision. |
| 6 | GLM-5.2 Max | `glm-5.2` | max | **62.00** | 434 | 49–70 | 24 | Could revise after correction, but repeatedly promoted working hypotheses into causal explanations, especially in long cases, and missed important retest or safety gaps. |
| 7 | DeepSeek V4 Pro Thinking | `deepseek-v4-pro` | high | **57.14** | 400 | 42–65 | 29 | Had the highest correction burden and the strongest recurrence of previously corrected errors in long context. Not suitable for unreviewed long-case work in this benchmark. |

Terra Medium and Luna Medium differ by only 0.14 points and should be treated as the same performance band rather than as a stable head-to-head ordering.

## Per-case scores

The labels below intentionally reveal no case content. They preserve the exact seven-case scores while keeping the underlying de-identified clinical workflow material private.

| Model route | Case 1 | Case 2 | Case 3 | Case 4 | Case 5 | Case 6 | Case 7 | Average |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sol Medium | 92 | 95 | 94 | 87 | 90 | 87 | 95 | **91.43** |
| Terra Medium | 87 | 92 | 87 | 90 | 85 | 87 | 92 | **88.57** |
| Luna Medium | 93 | 89 | 87 | 78 | 92 | 87 | 93 | **88.43** |
| Luna XHigh | 88 | 89 | 91 | 82 | 85 | 75 | 93 | **86.14** |
| Kimi K3 | 78 | 76 | 73 | 65 | 68 | 58 | 60 | **68.29** |
| GLM-5.2 Max | 68 | 69 | 65 | 51 | 62 | 49 | 70 | **62.00** |
| DeepSeek V4 Pro Thinking | 65 | 62 | 59 | 58 | 60 | 42 | 54 | **57.14** |

## What the score measures

Each case used a practitioner-reviewed 100-point rubric:

- revision after new evidence: 25 points;
- source fidelity: 25 points;
- question quality: 15 points;
- long-context consistency: 15 points;
- clinical collaboration utility: 15 points;
- interaction efficiency: 5 points.

Scores could recover after a correct response to new evidence, but an explicit correction did not erase an earlier source-fidelity failure, later recurrence, or correction overhead. One evaluator input incident was excluded for all seven routes and replaced with the same explicit input before scoring.

## Scope and limits

- This was a pure-text, no-tools, no-search, same-chat closed-loop benchmark.
- It does not measure images, audio, video, web research, tool use, or overall general intelligence.
- The scores measure behavior on an internal practitioner-authored workflow rubric. They are not clinical efficacy scores and do not authorize autonomous diagnosis or unreviewed case decisions.
- The underlying source material, full model outputs, and private clinical logic remain private. Only aggregate scores and sanitized assessment notes are published here.
- All 49 sessions and 49 human score entries completed validation. Actual model IDs matched on every successful provider/model call; no silent model substitution was detected.
