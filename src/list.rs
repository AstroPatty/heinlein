use clap::{Args, Parser, Subcommand};
use crate::util;
use console::Term;
use std::io::Result;

/// CLI tool to add new entries to a journal

#[derive(Args)]
pub(crate) struct ListArgs {
    /// (optional) The dataset to list
    pub(crate) dataset: Option<String>,
}

pub(crate) fn list(args: &ListArgs, term: &Term) -> Result<String>{
    match &args.dataset {
        Some(dataset) => {
            list_datatypes(dataset)
        },
        None => {
            list_datasets(term);
            Ok("".to_string())
        }
    }
}

fn list_datasets(term: &Term) {
    let datasets = util::list_ds();
    if datasets.len() == 0 {
        term.write_line("No datasets found").unwrap();
        return
    }
    term.write_line("Known datasets:").unwrap();
    for dataset in datasets {
        term.write_line(format!("\t{}", dataset).as_str()).unwrap();
    }
}

fn list_datatypes(dataset: &str) -> Result<String> {
    let datatypes = util::list_datatypes(dataset);
    match datatypes {
        Ok(datatypes) => {
            println!("Datatypes in dataset {}: ", dataset);
            for datatype in datatypes {
                println!("\t{}", datatype);
            }
            Ok((dataset).to_string())
        },
        Err(error) => {
            Err(error)
        }
    }


}