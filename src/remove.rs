use clap::{Args, Parser, Subcommand};

/// CLI tool to add new entries to a journal

#[derive(Args)]
pub(crate) struct RemoveArgs {
    pub(crate) dataset: String,
}