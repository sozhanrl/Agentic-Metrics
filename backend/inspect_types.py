import os
import pandas as pd

base_dir = r"E:\Metric project"
trivial_path = os.path.join(base_dir, "OnlyTrivial_dt.csv")
nontrivial_path = os.path.join(base_dir, "OnlyNonTrivial_dt.csv")

df_triv = pd.read_csv(trivial_path, nrows=5000)
print("Trivial head check:")
print("String columns:", df_triv.select_dtypes(include=['object', 'string']).columns.tolist())
print("Null count in trivial sample:", df_triv.isnull().sum()[df_triv.isnull().sum() > 0])
print("Type value counts in trivial sample:\n", df_triv['type'].value_counts())

df_nontriv = pd.read_csv(nontrivial_path, nrows=5000)
print("\nNonTrivial head check:")
print("String columns:", df_nontriv.select_dtypes(include=['object', 'string']).columns.tolist())
print("Null count in nontrivial sample:", df_nontriv.isnull().sum()[df_nontriv.isnull().sum() > 0])
print("Type value counts in nontrivial sample:\n", df_nontriv['type'].value_counts())
