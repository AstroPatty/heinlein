use clap::{Args, Parser, Subcommand};
use std::path::PathBuf;
use console::Term;
use crate::resource;
use serde_json::Value;
use std::collections::HashMap;
use std::io::Result;
/// CLI tool to add new entries to a journal

#[derive(Args)]
pub(crate) struct GetArgs {
    /// The name of the dataset
    pub(crate) dataset: String,
    /// The name of the datatype
    pub(crate) datatype: String,
}

pub(crate) fn get(args: &GetArgs, term: &Term) -> Result<PathBuf>  {

    let config: HashMap<String, Value>;
    match resource::load_config(&args.dataset) {
        Some((cfg, _)) => {
            config = cfg;
        },
        None => {
            return Err(std::io::Error::new(std::io::ErrorKind::NotFound,
                format!("Dataset {} does not exist", &args.dataset).to_string()));
        }
    }
    let data: HashMap<String, Value>;
    match config.get("data") {
        Some(data_value) => {
            data = serde_json::from_value(data_value.clone()).unwrap();
        },
        None => {
            return Err(std::io::Error::new(std::io::ErrorKind::NotFound,
                format!("Dataset {} does not contain any data", &args.dataset).to_string()));
        }
    }

    let path: PathBuf;
    match data.get(&args.datatype) {
        Some(path_value) => {
            path = PathBuf::from(path_value.as_str().unwrap());
            Ok(path)
        },
        None => {
            return Err(std::io::Error::new(std::io::ErrorKind::NotFound,
                format!("Dataset {} does not contain data of type {}", &args.dataset, &args.datatype).to_string()));
        }
    }
}

