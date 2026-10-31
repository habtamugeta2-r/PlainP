//! Checker: plain-sentence diagnostics — port of the oracle's checker.py.
//! Wording and hint style must stay identical to Python (the tests assert
//! on substrings shared by both suites). Suggestion engine differs in
//! mechanism (normalized Levenshtein vs difflib) but not in outcome.
use std::collections::HashMap;

use crate::ast::*;
use crate::errors::PlainError;
use crate::parser::{
    is_flag as known_flag, FLAGS, NODE_KINDS, SPECIAL_PROPS, VALUE_PROPS_1, VALUE_PROPS_EXPR,
};

const CHECKED_KINDS: &[&str] = &[
    "column", "row", "text", "button", "box", "image", "input", "toggle", "divider",
    "stack", "scroll", "grid", "spacer",
];

fn is_known_prop(w: &str) -> bool {
    VALUE_PROPS_1.contains(&w)
        || VALUE_PROPS_EXPR.contains(&w)
        || SPECIAL_PROPS.contains(&w)
        || matches!(w, "material" | "part" | "retry" | "error")
}

fn known_props_all() -> Vec<&'static str> {
    let mut v: Vec<&str> = Vec::new();
    v.extend_from_slice(VALUE_PROPS_1);
    v.extend_from_slice(VALUE_PROPS_EXPR);
    v.extend_from_slice(SPECIAL_PROPS);
    v.extend_from_slice(&["material", "part", "retry", "error"]);
    v
}

fn levenshtein(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    let mut cur: Vec<usize> = vec![0; b.len() + 1];
    for i in 1..=a.len() {
        cur[0] = i;
        for j in 1..=b.len() {
            let cost = if a[i - 1] == b[j - 1] { 0 } else { 1 };
            cur[j] = (prev[j] + 1).min(cur[j - 1] + 1).min(prev[j - 1] + cost);
        }
        std::mem::swap(&mut prev, &mut cur);
    }
    prev[b.len()]
}

fn closest(word: &str, candidates: &[&str], cutoff: f64) -> Option<String> {
    let mut best: Option<(f64, &str)> = None;
    for cand in candidates {
        let d = levenshtein(word, cand) as f64;
        let max_len = word.chars().count().max(cand.chars().count()) as f64;
        let ratio = if max_len == 0.0 { 1.0 } else { 1.0 - d / max_len };
        if ratio >= cutoff && best.map(|(r, _)| ratio > r).unwrap_or(true) {
            best = Some((ratio, cand));
        }
    }
    best.map(|(_, c)| c.to_string())
}

pub fn check_program(program: &Program) -> Vec<PlainError> {
    let mut errors = Vec::new();
    for page in &program.pages {
        if page.path.is_none() && page.params.is_empty() {
            errors.push(
                PlainError::new(format!(
                    "Page `{}` has no address. Pages need one so people (and links) can reach them.",
                    page.name
                ))
                .at(page.line_no, "")
                .hint(format!("page {} at \"/\":", page.name)),
            );
            // Python renders no source line for this one; drop the filler:
            if let Some(e) = errors.last_mut() {
                e.line_text = None;
            }
        }
    }
    let mut owners: Vec<(&str, &[Stmt])> = Vec::new();
    for p in &program.pages {
        owners.push((&p.name, &p.body));
    }
    for c in &program.components {
        owners.push((&c.name, &c.body));
    }
    for (_name, body) in owners {
        let mut seen: HashMap<String, usize> = HashMap::new();
        let mut actions: Vec<&str> = Vec::new();
        for stmt in body {
            match stmt {
                Stmt::State { name, line_no, .. } | Stmt::Derived { name, line_no, .. } => {
                    if let Some(prev) = seen.get(name) {
                        errors.push(
                            PlainError::new(format!(
                                "`{name}` is already created on line {prev}. One name, one value — pick a different name for the second one."
                            ))
                            .at(*line_no, ""),
                        );
                        if let Some(e) = errors.last_mut() {
                            e.line_text = None;
                        }
                    }
                    seen.insert(name.clone(), *line_no);
                }
                Stmt::Action { name, .. } => actions.push(name.as_str()),
                _ => {}
            }
        }
        check_block(body, program, &mut errors, &actions);
    }
    errors
}

fn check_block(stmts: &[Stmt], program: &Program, errors: &mut Vec<PlainError>, actions: &[&str]) {
    for stmt in stmts {
        match stmt {
            Stmt::Node(n) => check_node(n, program, errors, actions),
            Stmt::If {
                then_body,
                else_body,
                ..
            } => {
                check_block(then_body, program, errors, actions);
                check_block(else_body, program, errors, actions);
            }
            Stmt::For { body, .. } => check_block(body, program, errors, actions),
            Stmt::When { branches, .. } => {
                for b in branches {
                    check_block(&b.body, program, errors, actions);
                }
            }
            Stmt::Raw {
                text,
                line_no,
                children,
            } => {
                check_block(children, program, errors, actions);
                let head = text
                    .split_whitespace()
                    .next()
                    .unwrap_or("")
                    .trim_end_matches(':');
                if !matches!(head, "go" | "return" | "transition" | "refresh") {
                    if let Some(sug) = closest(head, NODE_KINDS, 0.65) {
                        errors.push(
                            PlainError::new(format!(
                                "`{head}` isn't a thing PL knows how to draw."
                            ))
                            .at(*line_no, text.clone())
                            .hint(format!("did you mean `{sug}`?")),
                        );
                    }
                }
            }
            _ => {}
        }
    }
}

fn check_node(node: &Node, program: &Program, errors: &mut Vec<PlainError>, actions: &[&str]) {
    for ev in &node.events {
        if let Some(action_src) = &ev.action {
            let name = action_src.split('(').next().unwrap_or("").trim();
            if !actions.contains(&name) {
                let hint = match closest(name, actions, 0.6) {
                    Some(s) => format!("did you mean `to {s}`?"),
                    None => format!("write it as `to {name}:` in this page/component"),
                };
                let mut e = PlainError::new(format!(
                    "There's no action called `{name}` here for `on {}` to run.",
                    ev.name
                ))
                .hint(hint);
                e.line_no = Some(node.line_no);
                errors.push(e);
            }
        }
    }
    for p in &node.props {
        if p.name == "look" {
            check_look(&p.value, program, errors, node.line_no);
            if let Some(other) = &p.otherwise {
                check_look(&other.value, program, errors, node.line_no);
            }
        }
    }
    if node.kind == "button" || node.kind == "link" {
        if node.content.is_none()
            && node.content_expr.is_none()
            && node.prop("label").is_none()
            && node.children.is_empty()
        {
            let action_src = match node.events.first() {
                Some(ev) => {
                    let mut s = format!("on {}", ev.name);
                    if let Some(a) = &ev.action {
                        s.push_str(&format!(" {a}"));
                    }
                    s
                }
                None => String::new(),
            };
            let line = format!("{} {}", node.kind, action_src).trim().to_string();
            let hint = format!("{} \"Save\" {}", node.kind, action_src)
                .trim()
                .to_string();
            errors.push(
                PlainError::new(format!("`{}` needs something to show.", node.kind))
                    .at(node.line_no, line)
                    .hint(hint),
            );
        }
    }
    if node.kind == "text" && node.content.is_none() && node.content_expr.is_none() {
        let mut e = PlainError::new("`text` needs something to say.").hint("text \"Hello\"");
        e.line_no = Some(node.line_no);
        errors.push(e);
    }
    if CHECKED_KINDS.contains(&node.kind.as_str()) {
        for p in &node.props {
            if !is_known_prop(&p.name) && program.component(&p.name).is_none() {
                let hint = match closest(&p.name, &known_props_all(), 0.6) {
                    Some(s) => format!("did you mean `{s}`?"),
                    None => "see docs/03-pl-language-spec.md §4-5 for the property list"
                        .to_string(),
                };
                let mut e = PlainError::new(format!(
                    "`{}` has no property called `{}`.",
                    node.kind, p.name
                ))
                .hint(hint);
                e.line_no = Some(node.line_no);
                errors.push(e);
            }
        }
        for f in &node.flags {
            if !known_flag(&f.name)
                && !f.name.chars().next().map(|c| c.is_uppercase()).unwrap_or(false)
            {
                let sug = closest(&f.name, FLAGS, 0.6);
                if sug.is_some() || f.name.chars().count() > 2 {
                    let mut e = PlainError::new(format!(
                        "`{}` isn't a style word PL knows.",
                        f.name
                    ));
                    e.line_no = Some(node.line_no);
                    if let Some(s) = sug {
                        e = e.hint(format!("did you mean `{s}`?"));
                    }
                    errors.push(e);
                }
            }
        }
    }
    for ch in &node.children {
        match ch {
            Stmt::Node(n) => check_node(n, program, errors, actions),
            Stmt::If { .. } | Stmt::For { .. } | Stmt::When { .. } | Stmt::Raw { .. } => {
                check_block(std::slice::from_ref(ch), program, errors, actions)
            }
            _ => {}
        }
    }
}

fn check_look(value: &str, program: &Program, errors: &mut Vec<PlainError>, line_no: usize) {
    let name = value.trim();
    if program.look(name).is_none() {
        let mut e = PlainError::new(format!("There's no look called `{name}`."))
            .hint(format!("write it as `look {name}:` in this file"));
        e.line_no = Some(line_no);
        errors.push(e);
    }
}
