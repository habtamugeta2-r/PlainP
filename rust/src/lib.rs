//! PLAIN / PL — Rust production port (ADR-1), slice 1.
//!
//! Mirrors the Python spec-oracle in `src/plainlang/` module-for-module:
//! the oracle defines semantics (it was built first and carries the test
//! suite); this crate must match it test-for-test. See docs/06 §7.

pub mod ast;
pub mod checker;
pub mod errors;
pub mod parser;
pub mod tokens;

pub use checker::check_program;
pub use errors::PlainError;
pub use parser::{block_tree, parse_program};
