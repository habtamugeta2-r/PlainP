//! `plain-rs` — Rust CLI (slice 1: parse-check + block dump).
//! The full `plain run/check/render` parity arrives with later slices;
//! the Python oracle CLI (`./plain`) remains feature-complete meanwhile.
use std::process::ExitCode;

use plainlang::{block_tree, parse_program};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match (args.first().map(|s| s.as_str()), args.len()) {
        (Some("check"), n) if n >= 2 => {
            let mut bad = 0;
            for path in &args[1..] {
                match std::fs::read_to_string(path) {
                    Ok(src) => match parse_program(&src) {
                        Ok(prog) => {
                            let pages: Vec<&str> = prog.page_names();
                            let comps: Vec<&str> =
                                prog.components.iter().map(|c| c.name.as_str()).collect();
                            println!(
                                "{path}: OK — pages: {}; components: {}; needs: {}",
                                if pages.is_empty() { "no pages".into() } else { pages.join(", ") },
                                if comps.is_empty() { "no components".into() } else { comps.join(", ") },
                                if prog.needs.is_empty() { "nothing".into() } else { prog.needs.join(", ") },
                            );
                        }
                        Err(e) => {
                            eprintln!("{path}:\n{}\n", e.render());
                            bad += 1;
                        }
                    },
                    Err(_) => {
                        eprintln!(
                            "I can't find `{path}`. Check the name — PL files end in `.plain`."
                        );
                        bad += 1;
                    }
                }
            }
            if bad > 0 {
                ExitCode::FAILURE
            } else {
                ExitCode::SUCCESS
            }
        }
        (Some("block"), 2) => {
            let path = &args[1];
            match std::fs::read_to_string(path) {
                Ok(src) => match block_tree(&src) {
                    Ok(roots) => {
                        fn dump(lines: &[plainlang::ast::Line], depth: usize) {
                            for l in lines {
                                println!("{}{}", "  ".repeat(depth), l.text);
                                dump(&l.children, depth + 1);
                            }
                        }
                        dump(&roots, 0);
                        ExitCode::SUCCESS
                    }
                    Err(e) => {
                        eprintln!("{}", e.render());
                        ExitCode::FAILURE
                    }
                },
                Err(_) => {
                    eprintln!("I can't find `{path}`.");
                    ExitCode::FAILURE
                }
            }
        }
        _ => {
            eprintln!(
                "plain-rs (Rust engine, slice 1)\n\
                 usage: plain-rs check <file.plain>... | plain-rs block <file.plain>\n\
                 (full run/render parity lands in later slices — see docs/06)"
            );
            ExitCode::FAILURE
        }
    }
}
