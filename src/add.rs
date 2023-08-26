use clap::{Args, Parser, Subcommand};
use directories::ProjectDirs;
use crate::{util,
            dataset,
            resource};

use std::path::PathBuf;
use std::collections::HashMap;
use serde_json::{Value, Map};
use console::Term;
use std::io;

/// CLI tool to add new entries to a journal

#[derive(Args)]
pub(crate) struct AddArgs {
    /// The dataset to add the datatype to
    pub(crate) dataset: String,
    /// The data type to add
    pub(crate) datatype: String,
    /// The path to the data
    pub(crate) path: PathBuf,
    ///Overwrite existing data of this type
    #[clap(short, long)]
    pub(crate) overwrite: bool
}

pub(crate) fn add(args: &AddArgs, term: &Term) -> io::Result<(String, String)> {
    let exists = util::ds_exists(&args.dataset);
    let cfg: (HashMap<String, serde_json::Value>, PathBuf);
    if exists {
        cfg = resource::load_config(&args.dataset).unwrap();
    }    
    else  {
        
        loop {
            term.write_str("Dataset does not exist. Would you like to create it? (y/n) ")?;
            let result = term.read_char()?;
            match result.to_ascii_uppercase() {
                'Y' =>{
                    term.write_str(format!("Creating dataset {}", &args.dataset).as_str());
                    cfg = dataset::create_dataset(&args.dataset);
                    break
                }
                'N' => {
                    term.write_str("Exiting...");
                    return Err(std::io::Error::new(std::io::ErrorKind::NotFound, "Dataset does not exist"));
                }
                _ => term.write_str("Please enter y or n")?
            }
        }
    }
    let mut config = cfg.0;
    let path = cfg.1;
    //get the data field from the config
    let mut data: HashMap<String, serde_json::Value>;
    if config.contains_key("data") {
        data = serde_json::from_value(config.get("data").unwrap().clone()).unwrap();
    }
    else {
        data = HashMap::new();
    }

    if !args.overwrite && data.contains_key(&args.datatype) {
        return Err(std::io::Error::new(
            std::io::ErrorKind::AlreadyExists,
            format!("Data of type {} already exists. Use --overwrite/-o to overwrite", &args.datatype).as_str()));
    }
    println!("Adding data at path {}", args.path.display());
    if !args.path.exists() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            format!("Path {} does not exist", args.path.display()).as_str()));
    }
    let abs_path = args.path.canonicalize().unwrap();
    data.insert(args.datatype.clone(), serde_json::to_value(&abs_path).unwrap());
    config.insert(String::from("data"), serde_json::to_value(&data).unwrap());
    let file = std::fs::File::create(&path).unwrap();
    let mut writer = std::io::BufWriter::new(file);
    serde_json::to_writer_pretty(&mut writer, &config).unwrap();
    Ok(((&args.dataset).to_string(), (&args.datatype).to_string()))

}

