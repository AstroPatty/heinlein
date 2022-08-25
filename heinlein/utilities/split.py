from heinlein.config.config import globalConfig
from heinlein import dataset
import functools
from pathlib import Path
import multiprocessing as mp
import pandas as pd
import sqlite3

def split_catalog(args) -> None:
    files = [file for file in args.input_path.glob(f"*{args.input_format}")]
    files = [f for f in files if not f.name.startswith(".")]
    print(f"Found {len(files)} to read from")
    ds = dataset.load_current_config(args.survey_name)
    catalog_config = ds['data']['catalog']
    region_key = catalog_config['region']
    subregion_key = catalog_config.get("subregion", False)
    if args.threads > 1:
        mgr = mp.Manager()
        accessed = mgr.dict()
    else:
        accessed = {}
    
    
    if args.output_format == "sqlite":
        output_path = args.output / ".".join([args.survey_name, "db"])
        output_f = functools.partial(output_to_db, subregion_key = subregion_key, output_path=output_path, accessed=accessed)
    elif args.output_format == "csv":
        raise NotImplementedError("Only output to SQLite currently supported")
        output_f = functools.partial(output_to_csv, subregion_key = subregion_key, output_path=args.output, accessed=accessed)
    else:
        raise NotImplementedError

    if args.input_format == ".csv":
        f = functools.partial(_split_from_csv, region_key=region_key, subregion_key=subregion_key, output_func = output_f)
    else:
        raise NotImplementedError("Splitting from non-csv files not yet supported")

    
    with mp.Pool(args.threads) as p:
        p.map(f, files)

def _split_from_csv(file_path: Path, region_key, subregion_key, output_func, ):
    print(f"Working on file {file_path}")
    df = pd.read_csv(file_path)
    output = {}
    region = df[region_key].unique()
    region_splits = {reg: df[df[region_key] == reg] for reg in region}
    output_func(region_splits)

def output_to_csv():
    pass

def output_to_db(data, subregion_key, output_path, accessed):
    con = sqlite3.Connection(output_path)
    for region_key, region_values in data.items():
        if type(region_values) == pd.DataFrame: 
            try:
                already_accessed = accessed[region_key]
            except KeyError:
                already_accessed = False

            if not already_accessed:
                accessed[region_key] = True
            else:
                while True:
                    a = accessed[region_key]
                    if not a:
                        accessed[region_key] = True
                        break
            region_values.to_sql(str(region_key), con=con, if_exists = "append")
            if accessed:
                accessed[region_key] = False
    