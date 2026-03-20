# Evaluation Metrics Across Tasks

## 1. Overview

This repository evaluates multiple downstream task families, and each family is scored with a task-appropriate metric design rather than a single universal criterion. In broad terms, the codebase uses class-sensitive precision/recall/F1 for classification tasks, span-aware entity metrics for named entity recognition (NER), and thresholded semantic-similarity tallies for the advice-generation setting. The evaluation pipeline is therefore heterogeneous by design: each task is mapped to the error structure that the developers appear to consider most meaningful for that prediction problem.

At the implementation level, evaluation is always organized by `(method_name, model_name)` pairs. Predictions from all relevant test instances for a given method-model combination are grouped together, scored jointly, and then written out as aggregate reports. This design makes the reported numbers model-level and method-level summaries rather than per-example end metrics.

The repository currently contains three evaluation regimes:

1. Triage classification, scored over four mutually exclusive classes.
2. Harmfulness classification, scored over two mutually exclusive classes.
3. Medical NER, scored with four nervaluate-style entity matching schemes.

In addition, the repository includes an advice-generation comparison pipeline. This pipeline does not compute precision/recall/F1, but it still defines an evaluation rule and produces task-level summary statistics. Because the user requested a full account of evaluation across the codebase, it is documented here as well.

## 2. Classification Evaluation

### 2.1 Common evaluation structure

The triage and harmful classification pipelines follow the same evaluation pattern. A summary CSV is first constructed from the test-set folder structure. Each row records `model_name`, `method_name`, `expected`, and `predicted`, after which rows are grouped by `(model_name, method_name)` and evaluated jointly. The scoring function used in both cases is `sklearn.metrics.precision_recall_fscore_support` with an explicit label list, class-wise scoring (`average=None`), micro averaging, macro averaging, and `zero_division=0` ([triage-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/triage-results.py#L52), [harmful-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/harmful-results.py#L50)).

This means the repository reports:

- Per-class precision
- Per-class recall
- Per-class F1
- Per-class support
- Micro-averaged precision, recall, and F1
- Macro-averaged precision, recall, and F1

All numeric outputs are rounded to four decimal places before serialization ([triage-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/triage-results.py#L81), [harmful-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/harmful-results.py#L79)).

### 2.2 Formal definitions

For a class \(c\), let \(TP_c\), \(FP_c\), and \(FN_c\) denote the class-specific true positives, false positives, and false negatives. The repository uses the standard definitions:

\[
\mathrm{Precision}_c = \frac{TP_c}{TP_c + FP_c}
\]

\[
\mathrm{Recall}_c = \frac{TP_c}{TP_c + FN_c}
\]

\[
F1_c = \frac{2 \cdot \mathrm{Precision}_c \cdot \mathrm{Recall}_c}{\mathrm{Precision}_c + \mathrm{Recall}_c}
\]

If a denominator is zero, the implementation returns `0` rather than throwing an exception or producing an undefined value, because `zero_division=0` is passed to scikit-learn.

Macro-averaged scores are the arithmetic mean of class-wise scores across the predefined label set:

\[
\mathrm{Macro\text{-}F1} = \frac{1}{|C|}\sum_{c \in C} F1_c
\]

Micro-averaged scores are computed from globally accumulated decisions over the full label set, rather than averaging per-class metrics:

\[
\mathrm{Micro\text{-}Precision} = \frac{\sum_c TP_c}{\sum_c (TP_c + FP_c)}
\]

\[
\mathrm{Micro\text{-}Recall} = \frac{\sum_c TP_c}{\sum_c (TP_c + FN_c)}
\]

\[
\mathrm{Micro\text{-}F1} = \frac{2 \cdot \mathrm{Micro\text{-}Precision} \cdot \mathrm{Micro\text{-}Recall}}{\mathrm{Micro\text{-}Precision} + \mathrm{Micro\text{-}Recall}}
\]

Because these are single-label classification tasks with fixed label vocabularies, micro-F1 is effectively dominated by overall instance-level correctness over the included labels.

### 2.3 Triage classification

The triage task defines four valid labels ([triage-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/triage-results.py#L8)):

- `REASSURANCE_SELF_CARE`
- `ROUTINE_OUTPATIENT_VISIT`
- `INVESTIGATION_OR_SPECIALIST_REFERRAL`
- `URGENT_EMERGENCY_CARE`

The summary-generation step treats each case ID as one classification instance. The expected label is read from `ground_truth.json["type"]`, and the predicted label is read from `output.json["type"]` ([triage-summary.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/triage-summary.py#L42), [triage-summary.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/triage-summary.py#L77)). Therefore, the unit of analysis is one case-level decision per `(id, method, model)` tuple.

An important implementation detail is that grouping is performed after the summary CSV is built, so all cases for a given method-model pair contribute jointly to one confusion structure and one final set of metrics. The output JSON also records `num_samples`, which equals the number of case-level rows included for that pair ([triage-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/triage-results.py#L92)).

### 2.4 Harmfulness classification

The harmfulness task defines two valid labels ([harmful-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/harmful-results.py#L8)):

- `SAFE`
- `HARMFUL`

Unlike the triage task, the harmful summary script operates at the recommendation level rather than the case level. For each case, it loads the list of ground-truth recommendations and the list of predicted recommendations, then pairs them positionally with `zip(...)` and writes one evaluation row per aligned recommendation index ([harmful-summary.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/harmful-summary.py#L42), [harmful-summary.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/harmful-summary.py#L85)).

This design has two consequences. First, the unit of analysis is an individual recommendation, not an entire case. Second, if the number of predicted recommendations differs from the number of ground-truth recommendations, the script records an error message but still evaluates only up to the shorter length because of the positional `zip(...)` pairing ([harmful-summary.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/harmful-summary.py#L78)). Therefore, extra unmatched predictions or extra unmatched references are not directly converted into explicit false positives or false negatives at this summary-building stage; they are effectively omitted from the classification table after the mismatch warning.

Once the summary CSV is built, scoring proceeds exactly as in triage: class-wise, micro, and macro precision/recall/F1 are computed over all aligned recommendation-level rows for each method-model pair.

## 3. Named Entity Recognition Evaluation

### 3.1 General setup

NER evaluation is split into two stages. The first stage evaluates each sample independently with `nervaluate`, writing a `results.json` file under each model directory. The second stage aggregates those per-sample results across all sample IDs for each `(method, model)` combination, sums the underlying count statistics, and then recomputes precision, recall, and F1 from the aggregated counts ([ner-initial-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-initial-eval.py#L49), [ner-final-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-final-eval.py#L60)).

The entity vocabulary is fixed to seven medical entity types ([ner-initial-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-initial-eval.py#L17)):

- `SYMPTOM_SIGN`
- `DISEASE_CONDITION`
- `DRUG_MEDICATION`
- `TEST_INVESTIGATION`
- `TREATMENT_PROCEDURE`
- `ANATOMY_BODY_PART`
- `MEDICAL_SPECIALTY`

Ground truth and predictions are read from BIO-formatted token-label text files, with one token-label pair per tab-separated line. Blank lines and comment lines beginning with `#` are skipped ([ner-initial-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-initial-eval.py#L19)).

### 3.2 Sequence alignment policy

Before NER scoring is performed, the predicted label sequence is forcibly aligned in length to the ground-truth label sequence. If the prediction is shorter, it is padded with `O` labels. If it is longer, it is truncated to the ground-truth length ([ner-initial-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-initial-eval.py#L118)).

This is an important methodological choice. Padding with `O` treats missing predicted tokens as non-entities, which can increase missed entities but prevents a shape mismatch from aborting evaluation. Truncation discards surplus predicted labels beyond the reference length. Consequently, the reported NER metrics assume an aligned token sequence and absorb sequence-length discrepancies into the entity accounting logic rather than treating them as a separate failure mode.

### 3.3 Entity-level count statistics

For each entity type and for each nervaluate matching scheme, the pipeline retains the following raw counts in `results.json` and in the final aggregate output:

- `correct`
- `incorrect`
- `partial`
- `missed`
- `spurious`
- `actual`
- `possible`

These counts are the sufficient statistics used later to recompute precision, recall, and F1 at aggregate level ([ner-initial-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-initial-eval.py#L61), [ner-final-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-final-eval.py#L52)).

Conceptually:

- `correct` counts fully accepted matches under a given scheme.
- `incorrect` counts matches judged wrong under that scheme.
- `partial` counts partially matched spans when the scheme allows partial credit.
- `missed` counts reference entities with no accepted prediction.
- `spurious` counts predicted entities with no accepted reference.
- `actual` is the number of predicted entities considered in scoring.
- `possible` is the number of gold entities that could be recovered.

### 3.4 The four NER scoring schemes

The final aggregation script explicitly supports four schemes ([ner-final-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-final-eval.py#L45)):

1. `strict`
2. `exact`
3. `ent_type`
4. `partial`

The implementation groups these schemes into two formula families:

- `strict` and `exact` are both mapped to the exact-match formula.
- `ent_type` and `partial` are both mapped to the partial-credit formula.

This does not mean the schemes are semantically identical. Rather, the per-sample `nervaluate` stage produces different raw counts for each scheme, and the aggregation stage then applies a common formula family to each scheme’s own counts.

### 3.5 Exact-match family: strict and exact

For `strict` and `exact`, the aggregation script computes:

\[
\mathrm{Precision} = \frac{COR}{ACT}
\]

\[
\mathrm{Recall} = \frac{COR}{POS}
\]

\[
F1 = \frac{2PR}{P+R}
\]

where:

- \(COR\) is `correct`
- \(ACT\) is `actual`
- \(POS\) is `possible`

This is implemented in `compute_exact_metrics(...)` ([ner-final-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-final-eval.py#L27)).

Under this family, partial matches receive no direct credit in the precision or recall formula, even though `partial`, `incorrect`, `missed`, and `spurious` are still preserved in the output. In practical terms, these schemes reward only fully correct entity recoveries as defined by the corresponding nervaluate matching rule.

### 3.6 Partial-credit family: ent_type and partial

For `ent_type` and `partial`, the aggregation script computes:

\[
\mathrm{Precision} = \frac{COR + 0.5 \cdot PAR}{ACT}
\]

\[
\mathrm{Recall} = \frac{COR + 0.5 \cdot PAR}{POS}
\]

\[
F1 = \frac{2PR}{P+R}
\]

where \(PAR\) is the `partial` count. This is implemented in `compute_partial_metrics(...)` ([ner-final-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-final-eval.py#L36)).

Thus, a partial match receives half credit. This is the repository’s key relaxation relative to strict matching: boundary or type mismatches that still preserve some overlap can contribute positively, depending on the underlying scheme-specific counts returned by nervaluate.

### 3.7 Per-entity, macro, and micro reporting

The NER aggregation script produces three levels of summary for each method-model pair.

First, it reports per-entity metrics for every entity type and every supported scheme. These are computed after summing raw counts across all sample IDs for that entity and scheme ([ner-final-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-final-eval.py#L119)).

Second, it reports `macro_f1` separately for each scheme. This is not a macro average over precision and recall; it is specifically the arithmetic mean of per-entity F1 values:

\[
\mathrm{Macro\text{-}F1}_{scheme} = \frac{1}{|E|}\sum_{e \in E} F1_{e,scheme}
\]

where \(E\) is the set of entity types for which that scheme is present in the aggregated output ([ner-final-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-final-eval.py#L152)).

Third, it reports `micro_avg` separately for each scheme by summing `correct`, `incorrect`, `partial`, `missed`, `spurious`, `actual`, and `possible` across all entity types and then recomputing precision, recall, and F1 from those pooled counts ([ner-final-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-final-eval.py#L161)).

This micro computation is important. The repository does not average previously computed per-entity scores. Instead, it reconstructs a single global contingency structure across all entities before scoring, which is the principled way to obtain micro-level entity metrics.

### 3.8 Interpretation of the NER metrics

From a methodological standpoint, the NER setup deliberately exposes different notions of correctness:

- `strict` is the most conservative view and is appropriate when exact boundary and type fidelity matter.
- `exact` uses the exact-match formula as well, but relies on nervaluate’s own scheme-specific count construction.
- `ent_type` gives partial credit through the `0.5 * partial` term and is more tolerant of some boundary deviations when entity type evidence is still useful.
- `partial` is the most forgiving in that it explicitly values overlapping but imperfect spans.

The presence of all four schemes makes the NER evaluation multidimensional rather than single-number. In effect, the pipeline asks whether a system is correct under exact extraction, correct under exact typing with scheme-specific count logic, and still useful under more permissive partial-overlap interpretations.

## 4. Advice Generation Evaluation

### 4.1 Nature of the metric

The advice-generation pipeline is not evaluated with precision/recall/F1. Instead, it performs semantic matching between generated recommendations and ground-truth recommendations using sentence embeddings from `l3cube-pune/bengali-sentence-similarity-sbert` and cosine similarity ([advice-comparison.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/advice-comparison.py#L11), [advice-comparison.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/advice-comparison.py#L29)).

For each generated advice item, the pipeline computes cosine similarity against every ground-truth recommendation, identifies the highest-scoring reference item, and assigns the corresponding ground-truth label if the best similarity is at least `0.6`; otherwise, it assigns `UNKNOWN` ([advice-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/advice-results.py#L19), [advice-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/advice-results.py#L29)).

Formally, for generated advice \(g\) and reference set \(R\),

\[
r^* = \arg\max_{r \in R} \cos(\mathrm{emb}(g), \mathrm{emb}(r))
\]

and the assigned label is:

\[
\hat{y}(g)=
\begin{cases}
\mathrm{label}(r^*) & \text{if } \cos(\mathrm{emb}(g), \mathrm{emb}(r^*)) \ge 0.6 \\
\mathrm{UNKNOWN} & \text{otherwise}
\end{cases}
\]

### 4.2 Reported outputs

After labeling each generated advice item as `SAFE`, `HARMFUL`, or `UNKNOWN`, the script aggregates counts and percentages per `(method, model)` pair and writes a CSV with:

- `safe_count`
- `harmful_count`
- `unknown_count`
- `total`
- `safe_pct`
- `harmful_pct`
- `unknown_pct`

These percentages are simple relative frequencies, not calibration metrics and not classification metrics against a directly aligned gold sequence ([advice-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/advice-results.py#L87)).

### 4.3 Implications

This evaluation regime should be interpreted as a retrieval-style or semantic-proximity summary rather than a strict generative accuracy measure. Because each generated advice item is independently matched to its most similar reference item, the pipeline does not enforce one-to-one matching between generated and gold recommendations, nor does it compute precision/recall against an explicit gold alignment structure. It instead measures how many generated pieces of advice can be plausibly mapped to safe or harmful reference advice above a fixed semantic threshold.

## 5. Cross-Task Comparison

Across the repository, the metric design reflects task structure:

- Triage classification uses standard multiclass classification metrics on one label per case.
- Harmfulness classification uses standard binary classification metrics on one label per aligned recommendation.
- NER uses entity-level span matching with four alternative correctness schemes and both macro and micro aggregation.
- Advice generation uses thresholded semantic similarity and label-frequency summaries rather than precision/recall/F1.

The principal methodological difference is that the classification pipelines score discrete labels directly, whereas the NER pipeline scores structured spans and therefore must distinguish exact, type-based, and partial matches. The advice-generation pipeline goes one step further away from direct symbolic comparison and evaluates outputs through nearest-reference semantic similarity.

## 6. Implementation-Specific Caveats

Several details in the code materially affect how the numbers should be interpreted.

First, classification uses explicit label lists. Scores are therefore computed only with respect to the predefined labels in each task ([triage-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/triage-results.py#L8), [harmful-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/harmful-results.py#L8)).

Second, classification sets `zero_division=0`, so undefined precision or recall values are silently converted to zero rather than being left undefined or omitted ([triage-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/triage-results.py#L57), [harmful-results.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/harmful-results.py#L55)).

Third, harmfulness evaluation depends on positional alignment of recommendation lists and truncates mismatched list lengths through `zip(...)`, after emitting a warning ([harmful-summary.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/harmful-summary.py#L78)).

Fourth, NER evaluation forces prediction length to match gold length through padding or truncation before calling nervaluate ([ner-initial-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-initial-eval.py#L118)).

Fifth, NER aggregation is count-based and therefore statistically sound at micro level: it recomputes final scores from pooled counts rather than averaging already-averaged sample scores ([ner-final-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-final-eval.py#L161)).

Finally, the repository’s NER `macro_f1` is the mean of per-entity F1 values for a given scheme, not a macro average over samples and not a macro average over precision and recall ([ner-final-eval.py](/home/aaniksahaa/research/doctalk/src/evaluation-pipeline-sadi/ner-final-eval.py#L152)).

## 7. Conclusion

In summary, the codebase implements a task-sensitive evaluation framework. Classification tasks are measured with conventional precision/recall/F1 summaries; NER is measured with multi-scheme entity-level F1 under both exact and partial-credit interpretations; and advice generation is summarized through thresholded semantic matching statistics. The resulting evaluation suite is therefore not reducible to a single universal metric, but instead expresses different operational definitions of correctness for different prediction problems. That design is methodologically reasonable for a multi-task medical evaluation pipeline, provided that reported results are always interpreted in the context of the exact task-specific metric family used.
