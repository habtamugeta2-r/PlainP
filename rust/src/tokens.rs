//! Shared line tokenizer for PL — port of the oracle's tokens.py.
//! Lexical decisions (docs/06): hyphenated names are single names
//! (subtraction needs spaces); `#` is a comment EXCEPT hex colors;
//! numbers carry unit suffixes or are ratios (`4/3`).

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TokKind {
    Str,
    Number,
    Color,
    Name,
    Op,
    Comma,
    Colon,
    LParen,
    RParen,
    LBracket,
    RBracket,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Tok {
    pub kind: TokKind,
    pub text: String,
}

impl Tok {
    fn new(kind: TokKind, text: impl Into<String>) -> Self {
        Tok {
            kind,
            text: text.into(),
        }
    }
    pub fn is_name(&self, words: &[&str]) -> bool {
        self.kind == TokKind::Name && words.iter().any(|w| *w == self.text)
    }
    pub fn is_op(&self, ops: &[&str]) -> bool {
        self.kind == TokKind::Op && ops.iter().any(|w| *w == self.text)
    }
}

/// If a hex color starts at chars[i]=='#', returns the full match as string.
fn match_color(chars: &[char], i: usize) -> Option<String> {
    if chars.get(i) != Some(&'#') {
        return None;
    }
    let hex: String = chars[i + 1..]
        .iter()
        .take_while(|c| c.is_ascii_hexdigit())
        .collect();
    if ![3usize, 6, 8].contains(&hex.len()) {
        return None;
    }
    let after = chars.get(i + 1 + hex.len());
    let ok_delim = match after {
        None => true,
        Some(c) => c.is_whitespace() || matches!(c, ',' | ')' | ']' | ':'),
    };
    if ok_delim {
        Some(format!("#{hex}"))
    } else {
        None
    }
}

/// Remove a trailing `#` comment, respecting strings and hex colors.
pub fn strip_comment(raw: &str) -> String {
    let chars: Vec<char> = raw.chars().collect();
    let mut in_str = false;
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c == '"' {
            in_str = !in_str;
        } else if c == '#' && !in_str {
            if match_color(&chars, i).is_some() {
                i += 1;
                continue;
            }
            let kept: String = chars[..i].iter().collect();
            return kept.trim_end().to_string();
        }
        i += 1;
    }
    raw.trim_end().to_string()
}

fn match_number(chars: &[char], i: usize) -> Option<(String, usize)> {
    if !chars.get(i).map(|c| c.is_ascii_digit()).unwrap_or(false) {
        return None;
    }
    let mut j = i;
    while chars.get(j).map(|c| c.is_ascii_digit()).unwrap_or(false) {
        j += 1;
    }
    // fraction
    if chars.get(j) == Some(&'.')
        && chars.get(j + 1).map(|c| c.is_ascii_digit()).unwrap_or(false)
    {
        j += 1;
        while chars.get(j).map(|c| c.is_ascii_digit()).unwrap_or(false) {
            j += 1;
        }
    }
    // ratio
    if chars.get(j) == Some(&'/')
        && chars.get(j + 1).map(|c| c.is_ascii_digit()).unwrap_or(false)
    {
        j += 1;
        while chars.get(j).map(|c| c.is_ascii_digit()).unwrap_or(false) {
            j += 1;
        }
    }
    // unit suffix (order matters: ms/deg before s)
    let rest: String = chars[j..].iter().take(3).collect();
    if rest.starts_with("ms") {
        j += 2;
    } else if rest.starts_with("deg") {
        j += 3;
    } else if rest.starts_with('s') || rest.starts_with('%') {
        j += 1;
    }
    Some((chars[i..j].iter().collect(), j))
}

fn match_name(chars: &[char], i: usize) -> Option<(String, usize)> {
    let first = *chars.get(i)?;
    if !(first.is_ascii_alphabetic() || first == '_') {
        return None;
    }
    let mut j = i + 1;
    while chars
        .get(j)
        .map(|c| c.is_ascii_alphanumeric() || *c == '_')
        .unwrap_or(false)
    {
        j += 1;
    }
    // hyphenated segments: -[A-Za-z0-9_]+ (part of ONE name)
    loop {
        if chars.get(j) == Some(&'-')
            && chars
                .get(j + 1)
                .map(|c| c.is_ascii_alphanumeric() || *c == '_')
                .unwrap_or(false)
        {
            j += 1;
            while chars
                .get(j)
                .map(|c| c.is_ascii_alphanumeric() || *c == '_')
                .unwrap_or(false)
            {
                j += 1;
            }
        } else {
            break;
        }
    }
    Some((chars[i..j].iter().collect(), j))
}

const OPS2: [&str; 6] = [">=", "<=", "+=", "-=", "==", "!="];
const OPS1: &str = "+-*/<>=.";

pub fn tokenize(text: &str) -> Vec<Tok> {
    let chars: Vec<char> = text.chars().collect();
    let mut toks = Vec::new();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c.is_whitespace() {
            i += 1;
            continue;
        }
        if c == '"' {
            match chars[i + 1..].iter().position(|&x| x == '"') {
                Some(rel) => {
                    let inner: String = chars[i + 1..i + 1 + rel].iter().collect();
                    toks.push(Tok::new(TokKind::Str, inner));
                    i = i + rel + 2;
                }
                None => {
                    let inner: String = chars[i + 1..].iter().collect();
                    toks.push(Tok::new(TokKind::Str, inner));
                    break;
                }
            }
            continue;
        }
        if let Some(col) = match_color(&chars, i) {
            i += col.chars().count();
            toks.push(Tok::new(TokKind::Color, col));
            continue;
        }
        if c.is_ascii_digit() {
            if let Some((num, j)) = match_number(&chars, i) {
                toks.push(Tok::new(TokKind::Number, num));
                i = j;
                continue;
            }
        }
        if let Some((name, j)) = match_name(&chars, i) {
            toks.push(Tok::new(TokKind::Name, name));
            i = j;
            continue;
        }
        let two: String = chars[i..].iter().take(2).collect();
        if OPS2.contains(&two.as_str()) {
            toks.push(Tok::new(TokKind::Op, two));
            i += 2;
            continue;
        }
        if OPS1.contains(c) {
            toks.push(Tok::new(TokKind::Op, c.to_string()));
            i += 1;
            continue;
        }
        let kind = match c {
            ',' => TokKind::Comma,
            ':' => TokKind::Colon,
            '(' => TokKind::LParen,
            ')' => TokKind::RParen,
            '[' => TokKind::LBracket,
            ']' => TokKind::RBracket,
            _ => TokKind::Name, // any other char (unicode symbol) — never crash
        };
        toks.push(Tok::new(kind, c.to_string()));
        i += 1;
    }
    toks
}

/// Rebuild readable source text from tokens (for expression strings).
pub fn detokenize(toks: &[Tok]) -> String {
    let mut out = String::new();
    let mut prev: Option<&Tok> = None;
    for t in toks {
        let s: String = if t.kind == TokKind::Str {
            format!("\"{}\"", t.text)
        } else {
            t.text.clone()
        };
        match prev {
            None => out.push_str(&s),
            Some(p) => {
                let tight = matches!(t.kind, TokKind::Comma | TokKind::RParen | TokKind::RBracket)
                    || t.text == "."
                    || matches!(p.kind, TokKind::LParen | TokKind::LBracket)
                    || p.text == "."
                    || (t.kind == TokKind::LParen && p.kind == TokKind::Name)
                    || t.kind == TokKind::Colon;
                if tight {
                    out.push_str(&s);
                } else {
                    out.push(' ');
                    out.push_str(&s);
                }
            }
        }
        prev = Some(t);
    }
    out.trim().to_string()
}
