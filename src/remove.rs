use clap::{Args, Parser, Subcommand};
use std::io::Result;
use std::collections::HashMap;
use std::path::PathBuf;
use serde_json::Value;

use crate::{util, resource};

/// CLI tool to add new entries to a journal

#[derive(Args)]
pub(crate) struct RemoveArgs {
    pub(crate) dataset: String,
    pub(crate) datatype: String,
}

pub(crate) fn remove(args: &RemoveArgs) -> Result<(String, String)> {
    let config: (HashMap<String, Value>, PathBuf);
    match resource::load_config(&args.dataset) {
        Some(cfg) => {
            config = cfg;
        },
        None => {
            return Err(std::io::Error::new(std::io::ErrorKind::NotFound,
                format!("Dataset {} does not exist", &args.dataset).to_string()));
        }
    }
    let mut config_data = config.0;
    if !config_data.contains_key("data") {
        return Err(std::io::Error::new(std::io::ErrorKind::NotFound,
            format!("Dataset {} does not contain any data", &args.dataset).to_string()));
    }
    let mut data: HashMap<String, Value> = serde_json::from_value(config_data.get("data").unwrap().clone()).unwrap();
    if !data.contains_key(&args.datatype) {
        return Err(std::io::Error::new(std::io::ErrorKind::NotFound,
            format!("Dataset {} does not contain data of type {}", &args.dataset, &args.datatype).to_string()));
    }
    data.remove(&args.datatype);
    config_data.insert("data".to_string(), serde_json::to_value(&data).unwrap());
    let file = std::fs::File::create(&config.1).unwrap();
    let mut writer = std::io::BufWriter::new(file);
    serde_json::to_writer_pretty(&mut writer, &config_data).unwrap();
    Ok(((&args.dataset).to_string(), "test".to_string()))

}