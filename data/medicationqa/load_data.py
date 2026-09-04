from datasets import load_dataset
import pandas as pd

dataset = load_dataset("truehealth/medicationqa")

df = dataset['train'].to_pandas()
df.to_csv('datasets/medicationqa.csv', index=False)

# clean up data: no answers, duplicates, no whitespace
original_length = len(df)

df = df.dropna(subset=['Question', 'Answer'])

df["Question"] = df["Question"].str.strip()
df["Answer"] = df["Answer"].str.strip()

no_answers = ["no answers", "unanswerable", "n/a", "none"]
df = df[~df["Answer"].str.lower().isin(no_answers)]

df = df.drop_duplicates()

df = df.reset_index(drop=True)

df.to_csv('datasets/medicationqa_cleaned.csv', index=False)

print(f"Original number of rows: {original_length}")
print(f"Number of rows after cleaning: {len(df)}")
print(f"Number of rows removed: {original_length - len(df)}")