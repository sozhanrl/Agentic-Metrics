import os
import pandas as pd
import numpy as np

base_dir = r"E:\Metric project"
defect_path = os.path.join(base_dir, "SoftwareDefectDataset.csv")
trivial_path = os.path.join(base_dir, "OnlyTrivial_dt.csv")
nontrivial_path = os.path.join(base_dir, "OnlyNonTrivial_dt.csv")

print("=" * 60)
print("1. SoftwareDefectDataset.csv")
print("=" * 60)
if os.path.exists(defect_path):
    df_def = pd.read_csv(defect_path)
    print(f"Shape: {df_def.shape}")
    print(f"Columns ({len(df_def.columns)}): {df_def.columns.tolist()}")
    print("Missing count:", df_def.isnull().sum().to_dict())
    print("Target distribution (DEFECT_LABEL):")
    print(df_def['DEFECT_LABEL'].value_counts(normalize=True))
    print(df_def['DEFECT_LABEL'].value_counts())
    print("\nDescribe summary:")
    print(df_def.describe().T[['mean', 'std', 'min', '50%', 'max']])
else:
    print("NOT FOUND:", defect_path)

print("\n" + "=" * 60)
print("2. OnlyTrivial_dt.csv")
print("=" * 60)
if os.path.exists(trivial_path):
    # Read sample first to see columns and types efficiently
    df_triv_head = pd.read_csv(trivial_path, nrows=100)
    print(f"Sample columns ({len(df_triv_head.columns)}): {df_triv_head.columns.tolist()}")
    # Read full file or chunk
    df_triv = pd.read_csv(trivial_path)
    print(f"Shape: {df_triv.shape}")
    if 'refactoring' in df_triv.columns:
        print("Target distribution ('refactoring'):")
        print(df_triv['refactoring'].value_counts(dropna=False))
        print("Normalized:")
        print(df_triv['refactoring'].value_counts(normalize=True, dropna=False))
    # Unique files / classes
    for col in ['file', 'class', 'type']:
        if col in df_triv.columns:
            print(f"Unique {col}: {df_triv[col].nunique()}")
    print("Data types summary:")
    print(df_triv.dtypes.value_counts())
else:
    print("NOT FOUND:", trivial_path)

print("\n" + "=" * 60)
print("3. OnlyNonTrivial_dt.csv")
print("=" * 60)
if os.path.exists(nontrivial_path):
    df_nontriv = pd.read_csv(nontrivial_path)
    print(f"Shape: {df_nontriv.shape}")
    if 'refactoring' in df_nontriv.columns:
        print("Target distribution ('refactoring'):")
        print(df_nontriv['refactoring'].value_counts(dropna=False))
        print("Normalized:")
        print(df_nontriv['refactoring'].value_counts(normalize=True, dropna=False))
    for col in ['file', 'class', 'type']:
        if col in df_nontriv.columns:
            print(f"Unique {col}: {df_nontriv[col].nunique()}")
    
    # Overlap check between trivial and nontrivial
    if 'file' in df_triv.columns and 'file' in df_nontriv.columns:
        overlap_files = set(df_triv['file']).intersection(set(df_nontriv['file']))
        print(f"Overlapping files between Trivial and NonTrivial: {len(overlap_files)}")
    if 'class' in df_triv.columns and 'class' in df_nontriv.columns:
        overlap_classes = set(df_triv['class']).intersection(set(df_nontriv['class']))
        print(f"Overlapping classes between Trivial and NonTrivial: {len(overlap_classes)}")
else:
    print("NOT FOUND:", nontrivial_path)
