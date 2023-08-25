use directories::BaseDirs;
use std::path::PathBuf;

fn get_project_dir() -> PathBuf {
    let config_dir = BaseDirs::new()
                                .unwrap()
                                .config_dir()
                                .join("heinlein2")
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
