use clap::{Parser, Subcommand};
use console::Term;

mod add;
mod get;
mod list;
mod remove;
mod util;
mod dataset;
mod resource;

#[derive(Parser)]
#[command(author, version, about, long_about = None)]
#[command(propagate_version = true)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Add a dataype to a given dataset
    Add(add::AddArgs),
    /// Rmove a dataype from a given dataset
    Remove(remove::RemoveArgs),
    /// Get the path to a particular datatype in a given datset
    Get(get::GetArgs),
    /// List all datasets, or all datatypes in a given dataset
    List(list::ListArgs),
}

fn main() {
    let cli = Cli::parse();
    let term = Term::stdout();
    // You can check for the existence of subcommands, and if found use their
    // matches just as you would the top level cmd
    match &cli.command {
        Commands::Add(args) => {
            let result = add::add(args, &term);
            println!("{:?}", result);
        },
        Commands::Remove(name) => {
            println!("'myapp remove' was used, name is: {:?}", name.dataset)
        },
        Commands::Get(name) => {
            println!("'myapp get' was used, name is: {:?}", name.dataset)
        },
        Commands::List(name) => {
            println!("'myapp list' was used, name is: {:?}", name.dataset)
        },
    }
}
