use clap::{Args, Parser, Subcommand};

/// CLI tool to add new entries to a journal

#[derive(Args)]
pub(crate) struct GetArgs {
    pub(crate) dataset: String,
}