from nervaluate import Evaluator

# Example ground truth (tokens + labels)
data = [
("কোলোরেক্টাল","O"),
("ক্যান্সারের","O"),
("ক্ষেত্রে","O"),
("কি","O"),
("কি","O"),
("লক্ষণগুলো","O"),
("প্রকাশ","O"),
("পেলে","O"),
("একজন","O"),
("রোগী","O"),
("বুঝতে","O"),
("পারবেন","O"),
("তিনি","O"),
("এই","O")
]

# Extract BIO labels only
y_true = [[label for token, label in data]]

# Example model prediction
y_pred = [[
"B-DISEASE_CONDITION",
"I-DISEASE_CONDITION",
"O",
"O",
"O",
"O",
"O",
"O",
"O",
"O",
"O",
"O",
"O",
"O"
]]

# Entity types present
tags = ["DISEASE_CONDITION"]

# Run evaluation
evaluator = Evaluator(y_true, y_pred, tags)

results = evaluator.evaluate()

print("Overall results:")
print(results)

# print("\nResults by entity type:")
# print(results_by_tag)