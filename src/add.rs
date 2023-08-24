use clap::{Args, Parser, Subcommand};

/// CLI tool to add new entries to a journal

#[derive(Args)]
pub(crate) struct AddArgs {
    /// The dataset to add the datatype to
    pub(crate) dataset: String,
    /// The data type to add
    pub(crate) datatype: String,
    #[clap(long, short = 'm')]
    /// The path to the data type
    pub(crate) path: Option<String>
}