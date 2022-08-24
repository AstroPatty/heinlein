from heinlein.config.config import globalConfig
import functools
from pathlib import Path
import multiprocessing as mp
import pandas as pd


def split_catalog(args) -> None:
    print(args)

def delegate_split(path: Path, key: str, threads = 1) -> None:
    files = [f for f in path.glob("*.csv") if not f.name.startswith(".")]
    print(f"Found {len(files)} files to split")
    func = functools.partial(_split, key=key)
    with mp.Pool(threads) as p:
        p.map(func, files)

def _split(file_path: Path, key: str):   
    print(f"Working on file {file_path}")
    df = pd.read_csv(file_path)
    try:
        split_by_data = df[key]
    except KeyError:
        print(f"File {file_path.name} has no column {key}, skipping...")
        return
    unique_names = split_by_data.unique()
    if len(unique_names) == len(split_by_data):
        print(f"Error: key {key} seems to be unique to all items!")
        return
    sub_dfs = {name: df[df[key] == name] for name in unique_names}
    output_path = file_path.parents[0]
    print(f"Writing outputs for file {file_path}")
    write_split_output_file(sub_dfs, output_path)


def write_split_output_file(dfs, output):
    for key, df in dfs.items():
        fpath = output / '.'.join([str(key), 'csv'])
        try:
            first = pd.read_csv(fpath)
            output_df = pd.concat([first, df])
        except:
            output_df = df

        with portalocker.Lock(fpath, 'w') as of:
            output_df.to_csv(of, index=False)
