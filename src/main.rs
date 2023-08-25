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
            match result {
                Ok((dataset, datatype)) => {
                    term.write_line(format!("Sucessfully added {} to {}", datatype, dataset).as_str()).unwrap();
                },
                Err(e) => {
                    term.write_line(format!("Error: {}", e).as_str()).unwrap();
                }

            }
        },
        Commands::Remove(args) => {
            let result = remove::remove(args);
            match result {
                Ok((dataset, datatype)) => {
                    term.write_line(format!("Sucessfully removed data `{}` from dataset `{}`", datatype, dataset).as_str()).unwrap();
                },
                Err(e) => {
                    term.write_line(format!("Error: {}", e).as_str()).unwrap();
                }

            }
        },
        Commands::Get(args) => {
            let result = get::get(args, &term);
            match result {
                Ok(path) => {
                    term.write_line(format!("{}", path.display()).as_str()).unwrap();
                },
                Err(e) => {
                    term.write_line(format!("Error: {}", e).as_str()).unwrap();
                }

            }
        },
        Commands::List(args) => {
            let result = list::list(&args, &term);
            match result {
                Err(e) => {
                    term.write_line(format!("Error: {}", e).as_str()).unwrap();
                },
                _ => ()
            }
        },
    }
}
