import pandas as pd
import traceback

csv_path = 'e:/Metric project/OnlyTrivial_dt.csv'
try:
    df = pd.read_csv(csv_path, nrows=500)
    print("Columns:", df.columns[:10])
    print("Refactoring counts:", df['refactoring'].value_counts())
    sample_size = 50
    df_sampled = df.groupby('refactoring', group_keys=False).apply(
        lambda x: x.sample(n=min(len(x), sample_size // 2), random_state=42)
    ).reset_index(drop=True)
    print("Sampled successfully, shape:", df_sampled.shape)
    print("Sampled cols has refactoring:", 'refactoring' in df_sampled.columns)
except Exception as e:
    print("ERROR:")
    traceback.print_exc()
