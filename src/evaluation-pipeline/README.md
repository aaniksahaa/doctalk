## Triage classification results -

* First generate summary.csv -> python triage-summary.py <FOLDER_PATH>
    - This will create a summary.csv with in the folder defined by the <FOLDER_PATH>
* Now generate the results -> python triage-results.py <PATH_TO_SUMMARY>
    - This will create a json inside the same folder as the script named triage_evaluation_results.json
    - You will find multiple entries , one for each method-model combination. Each entry will contain per-class precision, error, f1 and finnally summarized into micro and macro avg

## Triage classification results -

* First generate summary.csv -> python harmfule-summary.py <FOLDER_PATH>
    - This will create a summary.csv with in the folder defined by the <FOLDER_PATH>
* Now generate the results -> python harmful-results.py <PATH_TO_SUMMARY>
    - This will create a json inside the same folder as the script named harmful_evaluation_results.json
    - You will find multiple entries , one for each method-model combination. Each entry will contain per-class precision, error, f1 and finnally summarized into micro and macro avg

## NER results
* First generate BIO txt files -> python convert-to-bio.py <FOLDER_PATH>
    - This converts all the ground_truth.json and output.json to BIO txt file
* Generate initial results -> python ner-initial-eval.py <FOLDER_PATH>
    - For each model inference it generates a result by comparing it agaist the ground truth
* Generate final results -> python ner-final-eval.py <FOLDER_PATH>
    - Aggregates the results and generates 4 f1 for each entity and macro and micro avg. 
    - why 4 f1s -> they cover different factors and calculation is a little bit different.[Blog](https://www.davidsbatista.net/blog/2018/05/09/Named_Entity_Evaluation/)