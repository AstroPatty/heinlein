use std::path::PathBuf;
use crate::util;
use crate::resource;
use config::Config;
use std::collections::HashMap;
use std::fs;
use std::io::{BufWriter, Write};
use serde_json::{Value, to_value};

pub(crate) fn create_dataset(ds_name: &str) -> (HashMap<String, Value>, PathBuf) {
    let cfg_path = util::get_ds_dir();
    let ds_dir = cfg_path.join(&ds_name);
    if !ds_dir.exists() {
        std::fs::create_dir_all(&ds_dir).unwrap();
    }
    let mut config: HashMap<String, Value>;
    let mut known_config = resource::get_config_template(&ds_name);
    match known_config {
        Some(known_config) => {
            config = known_config;
        },
        None => {
            config = resource::get_default_config();
            config.insert(String::from("name"), serde_json::to_value(&ds_name).unwrap());
        }

    }


    let config_path = ds_dir.join("config.json");

    let file = fs::File::create(&config_path).unwrap();
    let mut writer = BufWriter::new(file);
    serde_json::to_writer_pretty(&mut writer, &config).unwrap();
    writer.flush().unwrap();

    (config, config_path)

}

