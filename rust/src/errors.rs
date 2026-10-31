//! Plain-sentence errors (Doc 03 §10: what, where, why, a concrete fix).
//! Port of the oracle's errors.py — wording must stay identical.
use std::fmt;

#[derive(Debug, Clone, PartialEq)]
pub struct PlainError {
    pub message: String,
    pub line_no: Option<usize>,
    pub line_text: Option<String>,
    pub hint: Option<String>,
}

impl PlainError {
    pub fn new(message: impl Into<String>) -> Self {
        PlainError {
            message: message.into(),
            line_no: None,
            line_text: None,
            hint: None,
        }
    }

    pub fn at(mut self, line_no: usize, line_text: impl Into<String>) -> Self {
        self.line_no = Some(line_no);
        self.line_text = Some(line_text.into());
        self
    }

    pub fn hint(mut self, hint: impl Into<String>) -> Self {
        self.hint = Some(hint.into());
        self
    }

    pub fn render(&self) -> String {
        let mut out = String::new();
        match self.line_no {
            Some(no) => out.push_str(&format!("Line {no}: {}", self.message)),
            None => out.push_str(&self.message),
        }
        if let Some(text) = &self.line_text {
            out.push_str(&format!("\n   {}", text.trim()));
        }
        if let Some(hint) = &self.hint {
            out.push_str(&format!("\nTry: {hint}"));
        }
        out
    }
}

impl fmt::Display for PlainError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.render())
    }
}

impl std::error::Error for PlainError {}
