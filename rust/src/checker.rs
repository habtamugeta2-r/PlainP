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

const SCOPED_CAPS: &[&str] = &["network", "native"];
const UNSCOPED_CAPS: &[&str] = &[
    "storage",
    "camera",
    "microphone",
    "location",
    "clipboard",
    "notifications",
    "gpu-compute",
];
const ALL_CAPS: &[&str] = &[
    "camera",
    "clipboard",
    "gpu-compute",
    "location",
    "microphone",
    "native",
    "network",
    "notifications",
    "storage",
];

fn clean_host_hint(tgt: &str) -> String {
    let with_scheme = if tgt.contains("://") {
        tgt.to_string()
    } else {
        format!("https://{tgt}")
    };
    let after = with_scheme.split_once("://").map_or("", |(_, r)| r);
    let end = after.find(&['/', '?', '#'][..]).unwrap_or(after.len());
    let host = &after[..end];
    if host.is_empty() {
        "api.example.com".to_string()
    } else {
        host.to_string()
    }
}

fn literal_resource_http_url(src: &str) -> Option<&str> {
    let s = src.trim();
    let s = s.strip_prefix("live ").map_or(s, |r| r.trim());
    let inner = s.strip_prefix('"')?.strip_suffix('"')?;
    if (inner.starts_with("http://") || inner.starts_with("https://"))
        && !inner.contains('{')
        && !inner.contains('"')
    {
        Some(inner)
    } else {
        None
    }
}

fn literal_request_http_url(src: &str) -> Option<&str> {
    let s = src.trim();
    let rest = s
        .strip_prefix("post ")
        .or_else(|| s.strip_prefix("fetch "))?
        .trim_start();
    let after_open = rest.strip_prefix('"')?;
    let close = after_open.find('"')?;
    let url = &after_open[..close];
    let tail = &after_open[close + 1..];
    if !tail.is_empty() && !tail.starts_with(char::is_whitespace) {
        return None;
    }
    if (url.starts_with("http://") || url.starts_with("https://")) && !url.contains('{') {
        Some(url)
    } else {
        None
    }
}

fn check_capabilities(program: &Program, errors: &mut Vec<PlainError>) {
    for cap in &program.capabilities {
        if cap.kind.is_empty() || cap.kind == "needs:" {
            errors.push(
                PlainError::new("`needs` must name at least one capability.")
                    .at(cap.line_no, cap.raw.clone())
                    .hint("needs network api.example.com"),
            );
            continue;
        }
        let raw_kind = cap.kind.trim_end_matches(':');
        if !ALL_CAPS.contains(&raw_kind) || cap.kind.ends_with(':') {
            let hint = match closest(raw_kind, ALL_CAPS, 0.6) {
                Some(s) => format!("did you mean `needs {s}`?"),
                None => "capabilities include `network <host>`, `storage`, `camera`, `clipboard`, `notifications`".to_string(),
            };
            errors.push(
                PlainError::new(format!("`{}` isn't a capability PL knows.", cap.kind))
                    .at(cap.line_no, cap.raw.clone())
                    .hint(hint),
            );
            continue;
        }
        if SCOPED_CAPS.contains(&cap.kind.as_str()) {
            let Some(raw_tgt) = &cap.target else {
                let (what, example) = if cap.kind == "network" {
                    (
                        "the host it talks to (no blanket internet access)",
                        "needs network api.example.com",
                    )
                } else {
                    ("the library it loads", "needs native sqlite")
                };
                errors.push(
                    PlainError::new(format!("`needs {}` must name {what}.", cap.kind))
                        .at(cap.line_no, cap.raw.clone())
                        .hint(example),
                );
                continue;
            };
            if cap.kind == "network" {
                let tgt = raw_tgt.trim();
                if tgt.contains("://") || tgt.contains('/') {
                    let clean_host = clean_host_hint(tgt);
                    errors.push(
                        PlainError::new(format!(
                            "`needs network` takes a host name, not a full URL (`{tgt}`)."
                        ))
                        .at(cap.line_no, cap.raw.clone())
                        .hint(format!("needs network {clean_host}")),
                    );
                } else if tgt.contains('*') {
                    errors.push(
                        PlainError::new(format!(
                            "`needs network` cannot use a wildcard (`{tgt}`) — name each host explicitly."
                        ))
                        .at(cap.line_no, cap.raw.clone())
                        .hint("needs network api.example.com"),
                    );
                } else if tgt.chars().any(char::is_whitespace) {
                    errors.push(
                        PlainError::new("Separate multiple capabilities with a comma in `needs`.")
                            .at(cap.line_no, cap.raw.clone())
                            .hint("needs network api.example.com, storage"),
                    );
                }
            }
        } else if UNSCOPED_CAPS.contains(&cap.kind.as_str()) {
            if let Some(extra) = &cap.target {
                errors.push(
                    PlainError::new(format!(
                        "`needs {}` doesn't take `{extra}` after it.",
                        cap.kind
                    ))
                    .at(cap.line_no, cap.raw.clone())
                    .hint(format!("needs {}", cap.kind)),
                );
            }
        }
    }
}

fn check_url_capability(
    url: &str,
    line_no: usize,
    line_text: Option<&str>,
    program: &Program,
    errors: &mut Vec<PlainError>,
) {
    let (allowed, host) = program.allows_network_url(url);
    if allowed {
        return;
    }
    let suggest_host = if host.contains(':') && !host.starts_with("scheme") {
        host.split(':').next().unwrap_or(&host)
    } else {
        host.as_str()
    };
    let mut err = PlainError::new(format!(
        "This line connects to `{host}`, which isn't listed in `needs`."
    ))
    .hint(format!("add `needs network {suggest_host}` at the top of this file"));
    err.line_no = Some(line_no);
    if let Some(txt) = line_text {
        err.line_text = Some(txt.to_string());
    }
    errors.push(err);
}

fn check_request_text_capability(
    text: &str,
    line_no: usize,
    line_text: Option<&str>,
    program: &Program,
    errors: &mut Vec<PlainError>,
) {
    if let Some(url) = literal_request_http_url(text) {
        check_url_capability(url, line_no, line_text, program, errors);
    }
}

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
    check_capabilities(program, &mut errors);

    for stmt in &program.shared_decls {
        match stmt {
            Stmt::Resource {
                source, line_no, ..
            } => {
                if let Some(url) = literal_resource_http_url(source) {
                    check_url_capability(url, *line_no, None, program, &mut errors);
                }
            }
            Stmt::Keep { name, line_no } if !program.has_capability("storage") => {
                let mut err = PlainError::new(format!(
                    "`keep {name}` saves data on this device, so this file must declare `needs storage`."
                ))
                .hint("add `needs storage` at the top of this file");
                err.line_no = Some(*line_no);
                errors.push(err);
            }
            _ => {}
        }
    }

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
                Stmt::Keep { name, line_no } if !program.has_capability("storage") => {
                    let mut err = PlainError::new(format!(
                        "`keep {name}` saves data on this device, so this file must declare `needs storage`."
                    ))
                    .hint("add `needs storage` at the top of this file");
                    err.line_no = Some(*line_no);
                    errors.push(err);
                }
                Stmt::Resource {
                    source, line_no, ..
                } => {
                    if let Some(url) = literal_resource_http_url(source) {
                        check_url_capability(url, *line_no, None, program, &mut errors);
                    }
                }
                Stmt::Action { name, .. } => actions.push(name.as_str()),
                _ => {}
            }
        }
        check_block(body, program, &mut errors, true, &actions);
        for stmt in body {
            if let Stmt::Action {
                body: action_body, ..
            } = stmt
            {
                check_block(action_body, program, &mut errors, false, &actions);
            }
        }
    }
    errors
}

fn check_block(
    stmts: &[Stmt],
    program: &Program,
    errors: &mut Vec<PlainError>,
    visual: bool,
    actions: &[&str],
) {
    for stmt in stmts {
        match stmt {
            Stmt::Node(n) => check_node(n, program, errors, actions),
            Stmt::Assign { expr, line_no, .. } => {
                check_request_text_capability(expr, *line_no, None, program, errors);
            }
            Stmt::If {
                then_body,
                else_body,
                line_no,
                inline_then,
                ..
            } => {
                if let Some(inl) = inline_then {
                    check_request_text_capability(inl, *line_no, None, program, errors);
                }
                check_block(then_body, program, errors, visual, actions);
                check_block(else_body, program, errors, visual, actions);
            }
            Stmt::For { body, .. } => check_block(body, program, errors, visual, actions),
            Stmt::When { branches, .. } => {
                for b in branches {
                    check_block(&b.body, program, errors, visual, actions);
                }
            }
            Stmt::Raw {
                text,
                line_no,
                children,
            } => {
                check_request_text_capability(text, *line_no, Some(text.as_str()), program, errors);
                check_block(children, program, errors, visual, actions);
                let words: Vec<&str> = text.split_whitespace().collect();
                let head = words.first().copied().unwrap_or("").trim_end_matches(':');
                if visual {
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
                } else {
                    let allowed = matches!(
                        head,
                        "go" | "return"
                            | "transition"
                            | "refresh"
                            | "show"
                            | "post"
                            | "fetch"
                            | "then"
                            | "together"
                            | "wait"
                    );
                    let is_list_op = words.len() > 1 && matches!(words[1], "add" | "remove");
                    if !head.is_empty()
                        && !allowed
                        && !is_list_op
                        && !head.starts_with("add")
                        && !head.starts_with("remove")
                    {
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
        if let Some(inline_src) = &ev.inline {
            let rhs = inline_src
                .split_once('=')
                .map_or(inline_src.as_str(), |(_, r)| r.trim());
            check_request_text_capability(rhs, node.line_no, None, program, errors);
        }
        if !ev.block.is_empty() {
            check_block(&ev.block, program, errors, false, actions);
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
                check_block(std::slice::from_ref(ch), program, errors, true, actions)
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
