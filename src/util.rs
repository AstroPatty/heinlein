use directories::BaseDirs;
use std::path::PathBuf;
use crate::resource;
use serde_json::Value;
use std::collections::HashMap;
use std::io::Result;

fn get_project_dir() -> PathBuf {
    let config_dir = BaseDirs::new()
                                .unwrap()
                                .config_dir()
                                .join("heinlein")
                                .to_path_buf();
    if !config_dir.exists() {
        std::fs::create_dir_all(&config_dir).unwrap();
    }
    config_dir
}

pub(crate) fn get_ds_dir() -> PathBuf {
    let config_dir = get_project_dir();
    let ds_dir = config_dir.join("datasets");
    if !ds_dir.exists() {
        std::fs::create_dir_all(&ds_dir).unwrap();
    }
    ds_dir

}

pub(crate) fn ds_exists(ds_name: &str) -> bool {
    let ds_dir = get_ds_dir();
    let ds_path = ds_dir.join(ds_name);
    let cfg_path = ds_path.join("config.json");
    cfg_path.exists()
}

pub(crate) fn list_ds() -> Vec<String> {
    let ds_dir = get_ds_dir();
    let mut ds_list: Vec<String> = Vec::new();
    for entry in std::fs::read_dir(ds_dir).unwrap() {
        let entry = entry.unwrap();
        let path = entry.path();
        if path.is_dir() {
            let ds_name = path.file_name().unwrap().to_str().unwrap().to_string();
            let cfg_path = path.join("config.json");
            if !cfg_path.exists() {
                continue;
            }
            ds_list.push(ds_name);
        }
    }
    ds_list
}

pub(crate) fn list_datatypes(ds_name: &str) -> Result<Vec<String>> {
    let cfg: HashMap<String, Value>;
    match resource::load_config(ds_name) {
        Some((cfg_data, _)) => {
            cfg = cfg_data
        },
        None => {
            return Err(std::io::Error::new(std::io::ErrorKind::NotFound, 
                format!("Dataset `{}` does not exist", ds_name).to_string()));
        }
    }
    let err = Err(std::io::Error::new(std::io::ErrorKind::NotFound,
        format!("Dataset {} does not contain any data", ds_name).to_string()));

    match cfg.get("data") {
        Some(data) => {
            let data: HashMap<String, Value> = serde_json::from_value(data.clone()).unwrap();
            let mut data_types: Vec<String> = Vec::new();
            for (key, _) in data {
                data_types.push(key);
            }
            if data_types.len() == 0 {
                return err
            }
            Ok(data_types)
        },
        None => {
            err
        }
    }

}