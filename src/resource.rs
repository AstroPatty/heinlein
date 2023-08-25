use serde_json::{Value, from_str};
use std::collections::HashMap;
use std::fs;
use include_dir::{include_dir, Dir};
use std::path::PathBuf;
use crate::util;
use std::fs::File;
use std::io::Read;

const SOURCE_DIR: Dir = include_dir!("$CARGO_MANIFEST_DIR/heinlein/config/datasets/");


pub(crate) fn get_config_template(name: &str) -> Option<HashMap<String, Value>> {
    let ds_config = SOURCE_DIR.get_file(format!("{}.json", name).as_str());
    match ds_config {
        Some(ds_config) => {
            let ds_config_contents = ds_config.contents_utf8().unwrap();
            let val: HashMap<String, serde_json::Value> = serde_json::from_str(&ds_config_contents).unwrap();
            Some(val)
        },
        None => None
    }
}

pub(crate) fn get_default_config() -> HashMap<String, Value> {
    let default_ds_config = SOURCE_DIR.get_file("default.json").unwrap();
    let default_config_contents = default_ds_config.contents_utf8().unwrap();
    let mut val: HashMap<String, serde_json::Value> = serde_json::from_str(&default_config_contents).unwrap();
    val
}
    
pub(crate) fn load_config(dsn: &str) -> Option<(HashMap<String, Value>, PathBuf)> {
    if !util::ds_exists(dsn) {
        return None;
    }
    let cfg_path = util::get_ds_dir();
    let ds_dir = cfg_path.join(&dsn);
    let config_path = ds_dir.join("config.json");
    let mut file = File::open(&config_path).unwrap();
    let mut fdata = String::new();
    file.read_to_string(&mut fdata).unwrap();
    let mut config_contents = serde_json::from_str(&fdata).unwrap();
    return Some((config_contents, config_path));
}
