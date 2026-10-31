//! PL parser: source → indentation block tree → classified AST.
//! Port of the oracle's parser.py; every grammar decision G-1…G-10
//! (docs/06 §5) is reproduced here and covered by the shared test cases.
//! Unknown lines become Raw statements — parsing the full normative
//! corpus (examples 00–08) must never crash.
use std::collections::HashMap;

use crate::ast::*;
use crate::errors::PlainError;
use crate::tokens::{detokenize, strip_comment, tokenize, Tok, TokKind};

// ---- vocabulary (single source of truth, shared with future checker) -------

pub fn is_node_kind(w: &str) -> bool {
    matches!(
        w,
        "column" | "row" | "stack" | "grid" | "scroll" | "box" | "text" | "image"
            | "video" | "audio" | "canvas" | "button" | "input" | "textarea" | "toggle"
            | "slider" | "select" | "link" | "divider" | "spacer" | "spinner" | "table"
            | "header" | "cell" | "scene3d" | "model3d" | "camera" | "light" | "children"
            | "material" | "part"
    )
}

fn is_value_prop1(w: &str) -> bool {
    matches!(
        w,
        "gap" | "size" | "color" | "background" | "corners" | "align" | "spread"
            | "label" | "placeholder" | "aspect" | "id" | "shape" | "fit" | "weight"
            | "font" | "opacity" | "enter" | "exit" | "shadow" | "bind" | "autocomplete"
            | "kind" | "columns" | "level" | "lines" | "ring"
    )
}

fn is_value_prop_expr(w: &str) -> bool {
    matches!(w, "error" | "value" | "scale" | "rotate-y" | "rotate" | "retry")
}

fn is_special_prop(w: &str) -> bool {
    matches!(
        w,
        "width" | "height" | "padding" | "animate" | "look" | "at" | "look-at" | "angle" | "stagger"
    )
}

pub fn is_flag(w: &str) -> bool {
    matches!(
        w,
        "bold" | "plain" | "primary" | "grow" | "center" | "center-self" | "strike"
            | "secret" | "capitalize" | "disabled" | "visible" | "stick-to-bottom"
            | "soft-shadows" | "italic" | "wrap"
    )
}

fn any_prop_start(w: &str) -> bool {
    is_value_prop1(w)
        || is_value_prop_expr(w)
        || is_special_prop(w)
        || is_flag(w)
        || matches!(w, "on" | "if" | "otherwise")
}

fn is_content_kind(w: &str) -> bool {
    matches!(w, "text" | "button" | "cell" | "image" | "link" | "video" | "model3d")
}

// ---- stage 1+2: logical lines & block tree ----------------------------------

type LLine = (usize, usize, String); // (line_no, indent_spaces, text)

pub fn logical_lines(source: &str) -> Result<Vec<LLine>, PlainError> {
    let mut raw: Vec<LLine> = Vec::new();
    for (idx, rawline) in source.lines().enumerate() {
        let no = idx + 1;
        let leading_ws: String = rawline.chars().take_while(|c| c.is_whitespace()).collect();
        if leading_ws.contains('\t') {
            return Err(PlainError::new(
                "Tabs for indentation get confusing fast — PL uses 2 spaces per level.",
            )
            .at(no, rawline)
            .hint("replace each tab with 2 spaces"));
        }
        let code = strip_comment(rawline);
        if code.trim().is_empty() {
            continue;
        }
        let indent = code.chars().take_while(|c| *c == ' ').count();
        let text = code.trim().to_string();
        if (text.starts_with("or ") || text.starts_with("and ")) && !raw.is_empty() {
            let last = raw.last_mut().unwrap();
            last.2.push(' ');
            last.2.push_str(&text);
            continue;
        }
        raw.push((no, indent, text));
    }
    for (no, indent, text) in &raw {
        if indent % 2 != 0 {
            return Err(PlainError::new(format!(
                "This line is indented {indent} spaces. PL indents 2 spaces at a time, \
                 so this one's halfway between levels."
            ))
            .at(*no, text.clone())
            .hint(format!("indent it {} or {} spaces", indent - 1, indent + 1)));
        }
    }
    Ok(raw)
}

fn jump_error(no: usize, text: &str) -> PlainError {
    PlainError::new(
        "This line jumps in more than one level. Indent one step (2 spaces) \
         at a time so nesting stays obvious.",
    )
    .at(no, text)
}

fn build_level(lines: &[LLine], idx: &mut usize, level: usize) -> Result<Vec<Line>, PlainError> {
    let mut out = Vec::new();
    while *idx < lines.len() {
        let (no, indent, text) = &lines[*idx];
        let lv = indent / 2;
        if lv < level {
            break;
        }
        if lv > level {
            return Err(jump_error(*no, text));
        }
        *idx += 1;
        let mut node = Line {
            text: text.clone(),
            no: *no,
            level: lv,
            children: Vec::new(),
        };
        if let Some((nno, nindent, ntext)) = lines.get(*idx) {
            let nlv = nindent / 2;
            if nlv > level {
                if nlv > level + 1 {
                    return Err(jump_error(*nno, ntext));
                }
                node.children = build_level(lines, idx, level + 1)?;
            }
        }
        out.push(node);
    }
    Ok(out)
}

pub fn block_tree(source: &str) -> Result<Vec<Line>, PlainError> {
    let lines = logical_lines(source)?;
    let mut idx = 0;
    build_level(&lines, &mut idx, 0)
}

// ---- header parsing (no regex dependency — mirrors the oracle's regexes) ----

fn parse_params(s: &str) -> Vec<String> {
    s.split(',')
        .map(|p| p.trim())
        .filter(|p| !p.is_empty())
        .map(|p| {
            p.split('=')
                .next()
                .unwrap_or("")
                .split(':')
                .next()
                .unwrap_or("")
                .trim()
                .to_string()
        })
        .collect()
}

/// Parse `Name` or `Name(params)` from a header fragment.
fn parse_name_params(frag: &str) -> Option<(String, Vec<String>)> {
    let frag = frag.trim();
    if frag.is_empty() {
        return None;
    }
    if let Some(open) = frag.find('(') {
        let name = frag[..open].trim().to_string();
        let close = frag.rfind(')')?;
        if name.is_empty() || name.contains(char::is_whitespace) {
            return None;
        }
        Some((name, parse_params(&frag[open + 1..close])))
    } else {
        if frag.contains(char::is_whitespace) {
            return None;
        }
        Some((frag.to_string(), Vec::new()))
    }
}

fn header_name(text: &str, kw: &str) -> Option<(String, Vec<String>)> {
    let rest = text.strip_prefix(kw)?.trim();
    let rest = rest.strip_suffix(':')?;
    parse_name_params(rest)
}

fn page_header(text: &str) -> Option<(String, Vec<String>, Option<String>)> {
    let rest = text.strip_prefix("page ")?.trim();
    let rest = rest.strip_suffix(':')?;
    let mut work = rest.to_string();
    let mut path = None;
    if let Some(at) = work.find(" at \"") {
        let tail = &work[at + 5..];
        let end = tail.find('"')?;
        path = Some(tail[..end].to_string());
        work = work[..at].to_string();
    }
    let (name, params) = parse_name_params(&work)?;
    if !name.chars().next().map(|c| c.is_uppercase()).unwrap_or(false) {
        return None;
    }
    Some((name, params, path))
}

fn kind_header(text: &str) -> Option<String> {
    let rest = text.strip_prefix("kind ")?.trim();
    let name = rest.strip_suffix(':')?.trim();
    if name.is_empty()
        || name.contains(char::is_whitespace)
        || !name.chars().next().map(|c| c.is_uppercase()).unwrap_or(false)
    {
        return None;
    }
    Some(name.to_string())
}

fn parse_kind_field(text: &str) -> Option<KindField> {
    let text = text.trim();
    let name_end = text
        .find(|c: char| c == ' ' || c == ':' || c == '=')
        .unwrap_or(text.len());
    let name = text[..name_end].to_string();
    if name.is_empty() {
        return None;
    }
    let mut rest = text[name_end..].trim_start();
    let mut type_hint = None;
    if let Some(after) = rest.strip_prefix(':') {
        let after = after.trim_start();
        match after.find('=') {
            Some(eq) => {
                type_hint = Some(after[..eq].trim().to_string());
                rest = &after[eq..];
            }
            None => {
                type_hint = Some(after.trim().to_string());
                rest = "";
            }
        }
    }
    let default = rest
        .strip_prefix('=')
        .map(|d| d.trim().to_string());
    Some(KindField {
        name,
        type_hint,
        default,
    })
}

// ---- program -----------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Eq)]
enum Ctx {
    Decls,
    Actions,
}

enum Classified {
    Stmt(Stmt),
    Otherwise,
    OtherwiseBody(Vec<Stmt>),
}

pub fn parse_program(source: &str) -> Result<Program, PlainError> {
    let roots = block_tree(source)?;
    let mut sigs: HashMap<String, Vec<String>> = HashMap::new();
    for ln in &roots {
        if let Some((name, params)) = header_name(&ln.text, "component") {
            sigs.insert(name, params);
        }
    }
    let par = Parser { sigs };
    let mut prog = Program::default();
    for ln in &roots {
        let t = &ln.text;
        if let Some(rest) = t.strip_prefix("needs ") {
            prog.needs.extend(
                rest.replace(',', " ")
                    .split_whitespace()
                    .map(|w| w.to_string()),
            );
        } else if let Some(name) = kind_header(t) {
            let fields = ln
                .children
                .iter()
                .filter_map(|ch| parse_kind_field(&ch.text))
                .collect();
            prog.kinds.push(KindDecl {
                name,
                fields,
                line_no: ln.no,
            });
        } else if let Some((name, params)) = header_name(t, "component") {
            let body = par.classify_block(&ln.children, Ctx::Decls)?;
            prog.components.push(Component {
                name,
                params,
                body,
                line_no: ln.no,
            });
        } else if let Some((name, params, path)) = page_header(t) {
            let body = par.classify_block(&ln.children, Ctx::Decls)?;
            prog.pages.push(Page {
                name,
                params,
                path,
                body,
                line_no: ln.no,
            });
        } else if let Some(name) = t
            .strip_prefix("look ")
            .and_then(|r| r.trim().strip_suffix(':'))
            .map(|n| n.trim())
            .filter(|n| !n.is_empty() && !n.contains(char::is_whitespace))
        {
            let mut look = LookDecl {
                name: name.to_string(),
                line_no: ln.no,
                ..Default::default()
            };
            for ch in &ln.children {
                let mut holder = Node::new("box", ch.no);
                par.prop_loop(&tokenize(&ch.text), &mut holder);
                look.props.append(&mut holder.props);
                look.flags.append(&mut holder.flags);
            }
            prog.looks.push(look);
        } else if t == "theme:" || (t.starts_with("theme ") && t.ends_with(':')) {
            prog.deferred.push(Stmt::Raw {
                text: t.clone(),
                line_no: ln.no,
                children: Vec::new(),
            });
        } else if t.starts_with("shared ") {
            match par.classify_stmt(ln, Ctx::Decls)? {
                Classified::Stmt(s) => prog.shared_decls.push(s),
                _ => prog.deferred.push(Stmt::Raw {
                    text: t.clone(),
                    line_no: ln.no,
                    children: Vec::new(),
                }),
            }
        } else if t.starts_with("use ") {
            prog.deferred.push(Stmt::Raw {
                text: t.clone(),
                line_no: ln.no,
                children: Vec::new(),
            });
        } else {
            prog.deferred.push(Stmt::Raw {
                text: t.clone(),
                line_no: ln.no,
                children: par.classify_block(&ln.children, Ctx::Decls)?,
            });
        }
    }
    Ok(prog)
}

// ---- classification -------------------------------------------------------------

struct Parser {
    sigs: HashMap<String, Vec<String>>,
}

impl Parser {
    fn classify_block(&self, lines: &[Line], ctx: Ctx) -> Result<Vec<Stmt>, PlainError> {
        let mut out: Vec<Stmt> = Vec::new();
        for ln in lines {
            match self.classify_stmt(ln, ctx)? {
                Classified::Stmt(s) => out.push(s),
                Classified::Otherwise => {
                    let body = self.classify_block(&ln.children, ctx)?;
                    attach_else(&mut out, body, ln)?;
                }
                Classified::OtherwiseBody(body) => attach_else(&mut out, body, ln)?,
            }
        }
        Ok(out)
    }

    fn classify_stmt(&self, ln: &Line, ctx: Ctx) -> Result<Classified, PlainError> {
        let t = &ln.text;
        let toks = tokenize(t);
        let head: &str = toks.first().map(|x| x.text.as_str()).unwrap_or("");

        if head == "to" {
            if let Some((name, params)) = header_name(t, "to") {
                return Ok(Classified::Stmt(Stmt::Action {
                    name,
                    params,
                    body: self.classify_block(&ln.children, Ctx::Actions)?,
                    line_no: ln.no,
                }));
            }
        }
        if head == "keep" {
            if let Some(name) = t.strip_prefix("keep ").map(|r| r.trim()).filter(|n| {
                !n.is_empty() && !n.contains(char::is_whitespace)
            }) {
                return Ok(Classified::Stmt(Stmt::Keep {
                    name: name.to_string(),
                    line_no: ln.no,
                }));
            }
        }
        if head == "if" {
            let rest = t.strip_prefix("if").unwrap_or("").trim();
            let (cond, inline) = split_colon(rest);
            return Ok(Classified::Stmt(Stmt::If {
                condition: cond,
                then_body: self.classify_block(&ln.children, ctx)?,
                else_body: Vec::new(),
                line_no: ln.no,
                inline_then: inline,
            }));
        }
        if head == "otherwise" {
            let rest = t.strip_prefix("otherwise").unwrap_or("").trim();
            if let Some(inner) = rest.strip_prefix("if ") {
                let _ = inner;
                let sub = Line {
                    text: rest.to_string(),
                    no: ln.no,
                    level: ln.level,
                    children: ln.children.clone(),
                };
                if let Classified::Stmt(s @ Stmt::If { .. }) = self.classify_stmt(&sub, ctx)? {
                    return Ok(Classified::OtherwiseBody(vec![s]));
                }
            } else if rest.is_empty() || rest == ":" {
                return Ok(Classified::Otherwise);
            }
        }
        if let Some(s) = self.try_for(ln, &toks, ctx)? {
            return Ok(Classified::Stmt(s));
        }
        if head == "when" {
            let rest = t.strip_prefix("when").unwrap_or("").trim();
            let (subject, _) = split_colon(rest);
            let mut branches = Vec::new();
            for ch in &ln.children {
                let (pat, inline) = if let Some(r) = ch.text.strip_prefix("is ") {
                    split_colon(r.trim())
                } else {
                    (ch.text.clone(), None)
                };
                let mut body = self.classify_block(&ch.children, ctx)?;
                if let Some(inline_text) = inline {
                    let sub = Line {
                        text: inline_text,
                        no: ch.no,
                        level: ch.level,
                        children: Vec::new(),
                    };
                    if let Classified::Stmt(s) = self.classify_stmt(&sub, ctx)? {
                        body.insert(0, s);
                    }
                }
                branches.push(WhenBranch {
                    pattern: pat.trim().to_string(),
                    body,
                    line_no: ch.no,
                });
            }
            return Ok(Classified::Stmt(Stmt::When {
                subject: subject.trim().to_string(),
                branches,
                line_no: ln.no,
            }));
        }
        if let Some(s) = self.try_decl(ln, &toks, ctx) {
            return Ok(Classified::Stmt(s));
        }
        let upper_first = head.chars().next().map(|c| c.is_uppercase()).unwrap_or(false);
        if is_node_kind(head)
            || (upper_first && toks.first().map(|x| x.kind) == Some(TokKind::Name))
            || self.sigs.contains_key(head)
        {
            return Ok(Classified::Stmt(Stmt::Node(self.parse_node(ln, ctx)?)));
        }
        Ok(Classified::Stmt(Stmt::Raw {
            text: t.clone(),
            line_no: ln.no,
            children: if ln.children.is_empty() {
                Vec::new()
            } else {
                self.classify_block(&ln.children, ctx)?
            },
        }))
    }

    fn try_for(&self, ln: &Line, toks: &[Tok], ctx: Ctx) -> Result<Option<Stmt>, PlainError> {
        if toks.len() < 4 || !toks[0].is_name(&["for"]) || toks[1].kind != TokKind::Name {
            return Ok(None);
        }
        let var = toks[1].text.clone();
        let mut i = 2;
        let mut index_var = None;
        if toks.get(i).map(|x| x.kind) == Some(TokKind::Comma)
            && toks.get(i + 1).map(|x| x.kind) == Some(TokKind::Name)
        {
            index_var = Some(toks[i + 1].text.clone());
            i += 2;
        }
        if toks.get(i).map(|x| !x.is_name(&["in"])).unwrap_or(true) {
            return Ok(None);
        }
        i += 1;
        let mut rest: Vec<Tok> = toks[i..].to_vec();
        if rest.last().map(|x| x.kind) == Some(TokKind::Colon) {
            rest.pop();
        }
        Ok(Some(Stmt::For {
            var,
            index_var,
            iterable: detokenize(&rest),
            body: self.classify_block(&ln.children, ctx)?,
            line_no: ln.no,
        }))
    }

    fn try_decl(&self, ln: &Line, toks: &[Tok], ctx: Ctx) -> Option<Stmt> {
        let shared = toks.first().map(|x| x.is_name(&["shared"])).unwrap_or(false);
        let work: &[Tok] = if shared { &toks[1..] } else { toks };
        if work.is_empty() || work[0].kind != TokKind::Name {
            return None;
        }
        let name = work[0].text.clone();
        if work.get(1).map(|x| x.is_name(&["from"])).unwrap_or(false) {
            return Some(Stmt::Resource {
                name,
                source: detokenize(&work[2..]),
                line_no: ln.no,
                shared,
            });
        }
        // name [: Type] = expr — LHS may only be names/colons/dots, so node
        // lines with handlers (`button "−1" on tap: count -= 1`) never match.
        let scan = work.len().min(8);
        let mut i = 0;
        while i < scan {
            let tok = &work[i];
            if i > 0
                && !(tok.kind == TokKind::Name
                    || tok.kind == TokKind::Colon
                    || tok.is_op(&[".", "=", "+=", "-="]))
            {
                break;
            }
            if tok.is_op(&["=", "+=", "-="]) {
                let lhs = &work[1..i];
                let type_hint = if lhs.first().map(|x| x.kind) == Some(TokKind::Colon) {
                    Some(detokenize(&lhs[1..]))
                } else {
                    None
                };
                let expr = detokenize(&work[i + 1..]);
                let dotted = work.get(1).map(|x| x.is_op(&["."])).unwrap_or(false);
                if ctx == Ctx::Decls && tok.text == "=" && !dotted {
                    return Some(Stmt::State {
                        name,
                        expr,
                        line_no: ln.no,
                        type_hint,
                        shared,
                    });
                }
                let target_full = detokenize(&work[..i]);
                let target = target_full
                    .split(':')
                    .next()
                    .unwrap_or("")
                    .trim()
                    .to_string();
                return Some(Stmt::Assign {
                    target,
                    op: tok.text.clone(),
                    expr,
                    line_no: ln.no,
                });
            }
            i += 1;
        }
        if work.len() > 2 && work[1].is_name(&["is"]) && ctx == Ctx::Decls {
            return Some(Stmt::Derived {
                name,
                expr: detokenize(&work[2..]),
                line_no: ln.no,
            });
        }
        if work.get(1).map(|x| x.is_name(&["add", "remove"])).unwrap_or(false) {
            return Some(Stmt::Raw {
                text: ln.text.clone(),
                line_no: ln.no,
                children: Vec::new(),
            });
        }
        None
    }

    // -- node lines ---------------------------------------------------------

    fn parse_node(&self, ln: &Line, ctx: Ctx) -> Result<Node, PlainError> {
        let mut toks = tokenize(&ln.text);
        if toks.last().map(|x| x.kind) == Some(TokKind::Colon) {
            toks.pop();
        }
        let kind = toks.first().map(|x| x.text.clone()).unwrap_or_default();
        let mut node = Node::new(&kind, ln.no);
        let mut rest: Vec<Tok> = toks.into_iter().skip(1).collect();

        // inline child after colon: `column ... : spinner`
        let mut inline_child: Option<String> = None;
        let mut depth: i32 = 0;
        let mut colon_at: Option<usize> = None;
        for (i, tok) in rest.iter().enumerate() {
            match tok.kind {
                TokKind::LParen | TokKind::LBracket => depth += 1,
                TokKind::RParen | TokKind::RBracket => depth -= 1,
                TokKind::Colon if depth == 0 => {
                    colon_at = Some(i);
                    break;
                }
                _ => {}
            }
        }
        if let Some(i) = colon_at {
            let before = &rest[..i];
            if !before.iter().any(|x| x.is_name(&["on"])) {
                inline_child = Some(detokenize(&rest[i + 1..]));
                rest = before.to_vec();
            }
        }

        let rest = self.content_and_args(&mut node, rest);
        self.prop_loop(&rest, &mut node);

        let mut visual: Vec<Line> = Vec::new();
        if let Some(ic) = inline_child {
            visual.push(Line {
                text: ic,
                no: ln.no,
                level: ln.level + 1,
                children: Vec::new(),
            });
        }
        for ch in &ln.children {
            let ctoks = tokenize(&ch.text);
            let chead: &str = ctoks.first().map(|x| x.text.as_str()).unwrap_or("");
            if chead == "on" {
                node.events.push(self.event_from_line(ch)?);
            } else if ctoks.get(1).map(|x| x.is_name(&["is"])).unwrap_or(false) {
                visual.push(ch.clone()); // scoped derivation (G-4)
            } else if (is_value_prop1(chead)
                || is_value_prop_expr(chead)
                || is_special_prop(chead)
                || is_flag(chead))
                && !is_node_kind(chead)
            {
                self.prop_loop(&ctoks, &mut node);
            } else {
                visual.push(ch.clone());
            }
        }
        node.children = self.classify_block(&visual, ctx)?;
        Ok(node)
    }

    fn content_and_args(&self, node: &mut Node, toks: Vec<Tok>) -> Vec<Tok> {
        if toks.is_empty() {
            return toks;
        }
        let first_upper = node
            .kind
            .chars()
            .next()
            .map(|c| c.is_uppercase())
            .unwrap_or(false);
        let is_component = first_upper || self.sigs.contains_key(&node.kind);
        let wants_content = is_content_kind(&node.kind) || is_component;
        if !wants_content {
            return toks;
        }
        let t0 = &toks[0];
        if t0.is_name(&["on"]) {
            return toks;
        }
        if t0.kind == TokKind::Str {
            if toks.get(1).map(|x| x.is_name(&["if"])).unwrap_or(false) {
                let end = conditional_string_end(&toks);
                node.content_expr = Some(detokenize(&toks[..end]));
                return toks[end..].to_vec();
            }
            node.content = Some(t0.text.clone());
            return toks[1..].to_vec();
        }
        let params: Vec<String> = self.sigs.get(&node.kind).cloned().unwrap_or_default();
        if t0.kind == TokKind::Name
            && (!is_component
                || (!any_prop_start(&t0.text) && !params.contains(&t0.text)))
        {
            // G-1: built-in content kinds always take content first.
            let mut i = 1;
            while toks.get(i).map(|x| x.is_op(&["."])).unwrap_or(false)
                && toks.get(i + 1).map(|x| x.kind) == Some(TokKind::Name)
            {
                i += 2;
            }
            if toks.get(i).map(|x| x.is_name(&["as"])).unwrap_or(false) && i + 1 < toks.len() {
                i += 2;
            }
            node.content_expr = Some(detokenize(&toks[..i]));
            return toks[i..].to_vec();
        }
        if t0.kind == TokKind::Number {
            node.content_expr = Some(t0.text.clone());
            return toks[1..].to_vec();
        }
        toks
    }

    // -- property loop ---------------------------------------------------------

    fn prop_loop(&self, toks: &[Tok], node: &mut Node) {
        let mut i = 0;
        let n = toks.len();
        let params: Vec<String> = self.sigs.get(&node.kind).cloned().unwrap_or_default();
        while i < n {
            let t = &toks[i];
            if matches!(t.kind, TokKind::Comma | TokKind::Colon) {
                i += 1;
                continue;
            }
            if t.is_name(&["on"]) {
                let (ev, ni) = event_from_tokens(toks, i);
                node.events.push(ev);
                i = ni;
                continue;
            }
            if t.kind != TokKind::Name {
                node.args.push(t.text.clone());
                i += 1;
                continue;
            }
            let word = t.text.clone();
            if word == "if" && (!node.props.is_empty() || !node.flags.is_empty()) {
                let (cond, ni) = capture_condition(toks, i + 1, &params);
                i = ni;
                if let Some(last) = node.props.last_mut() {
                    last.condition = Some(cond);
                } else if let Some(last) = node.flags.last_mut() {
                    last.condition = Some(cond);
                }
                if toks.get(i).map(|x| x.is_name(&["otherwise"])).unwrap_or(false) {
                    i += 1;
                    if toks.get(i).map(|x| x.kind) == Some(TokKind::Name) && !node.props.is_empty()
                    {
                        let o_name = toks[i].text.clone();
                        let (o_val, ni) = value_tokens(toks, i + 1, false, &params);
                        i = ni;
                        if let Some(last) = node.props.last_mut() {
                            last.otherwise = Some(Box::new(Prop {
                                name: o_name,
                                value: o_val,
                                condition: None,
                                otherwise: None,
                            }));
                        }
                    }
                }
                continue;
            }
            if is_special_prop(&word) {
                i = self.special_prop(&word, toks, i, node, &params);
                continue;
            }
            if is_value_prop1(&word) || is_value_prop_expr(&word) || params.contains(&word) {
                let free = is_value_prop_expr(&word) || params.contains(&word);
                i = value_prop(&word, toks, i, node, &params, free);
                continue;
            }
            if is_flag(&word) {
                i += 1;
                let mut flag = Flag {
                    name: word,
                    condition: None,
                };
                if toks.get(i).map(|x| x.is_name(&["if"])).unwrap_or(false) {
                    let (cond, ni) = capture_condition(toks, i + 1, &params);
                    i = ni;
                    flag.condition = Some(cond);
                }
                node.flags.push(flag);
                continue;
            }
            // unknown word: value-prop if followed by an obvious value
            let nxt = toks.get(i + 1);
            let value_like = nxt
                .map(|x| {
                    matches!(
                        x.kind,
                        TokKind::Str | TokKind::Number | TokKind::Color | TokKind::LBracket
                    ) || (x.kind == TokKind::Name
                        && !any_prop_start(&x.text)
                        && !params.contains(&x.text))
                })
                .unwrap_or(false);
            if value_like {
                i = value_prop(&word, toks, i, node, &params, false);
            } else {
                node.flags.push(Flag {
                    name: word,
                    condition: None,
                });
                i += 1;
            }
        }
    }

    fn special_prop(
        &self,
        word: &str,
        toks: &[Tok],
        i: usize,
        node: &mut Node,
        params: &[String],
    ) -> usize {
        let n = toks.len();
        match word {
            "padding" => {
                let mut vals = Vec::new();
                let mut j = i + 1;
                while toks.get(j).map(|x| x.kind) == Some(TokKind::Number) && vals.len() < 4 {
                    vals.push(toks[j].text.clone());
                    j += 1;
                }
                node.props.push(Prop {
                    name: "padding".into(),
                    value: vals.join(" "),
                    condition: None,
                    otherwise: None,
                });
                j
            }
            "width" | "height" => {
                let mut got = Vec::new();
                let mut j = i + 1;
                while j < n {
                    let x = &toks[j];
                    let ok = x.kind == TokKind::Number
                        || (x.kind == TokKind::Name
                            && ["fill", "fit", "max", "min"].contains(&x.text.as_str()));
                    if !ok {
                        break;
                    }
                    got.push(x.text.clone());
                    j += 1;
                }
                node.props.push(Prop {
                    name: word.into(),
                    value: got.join(" "),
                    condition: None,
                    otherwise: None,
                });
                j
            }
            "look" => {
                let (value, mut j) = value_tokens(toks, i + 1, false, params);
                let mut prop = Prop {
                    name: "look".into(),
                    value,
                    condition: None,
                    otherwise: None,
                };
                if toks.get(j).map(|x| x.is_name(&["if"])).unwrap_or(false) {
                    let (cond, ni) = capture_condition(toks, j + 1, params);
                    j = ni;
                    prop.condition = Some(cond);
                    if toks.get(j).map(|x| x.is_name(&["otherwise"])).unwrap_or(false) {
                        j += 1;
                        if toks.get(j).map(|x| x.is_name(&["look"])).unwrap_or(false) {
                            let (o_val, ni) = value_tokens(toks, j + 1, false, params);
                            j = ni;
                            prop.otherwise = Some(Box::new(Prop {
                                name: "look".into(),
                                value: o_val,
                                condition: None,
                                otherwise: None,
                            }));
                        }
                    }
                }
                node.props.push(prop);
                j
            }
            "animate" => {
                let mut got = Vec::new();
                let mut j = i + 1;
                while j < n
                    && toks[j].kind == TokKind::Name
                    && !any_prop_start(&toks[j].text)
                    && got.len() < 2
                {
                    got.push(toks[j].text.clone());
                    j += 1;
                }
                node.props.push(Prop {
                    name: "animate".into(),
                    value: got.join(" "),
                    condition: None,
                    otherwise: None,
                });
                j
            }
            "at" | "look-at" => {
                let mut got = Vec::new();
                let mut j = i + 1;
                while j < n
                    && (matches!(toks[j].kind, TokKind::Number | TokKind::Comma)
                        || toks[j].text == "-")
                {
                    got.push(toks[j].text.clone());
                    j += 1;
                }
                node.props.push(Prop {
                    name: word.into(),
                    value: got.join(" "),
                    condition: None,
                    otherwise: None,
                });
                j
            }
            _ => {
                let (value, j) = value_tokens(toks, i + 1, false, params);
                node.props.push(Prop {
                    name: word.into(),
                    value,
                    condition: None,
                    otherwise: None,
                });
                j
            }
        }
    }

    // -- events -------------------------------------------------------------

    fn event_from_line(&self, ln: &Line) -> Result<Event, PlainError> {
        let mut toks = tokenize(&ln.text);
        if toks.last().map(|x| x.kind) == Some(TokKind::Colon) && !ln.children.is_empty() {
            toks.pop();
        }
        let (mut ev, _) = event_from_tokens(&toks, 0);
        if !ln.children.is_empty() {
            ev.block = self.classify_block(&ln.children, Ctx::Actions)?;
        } else if let Some(inline) = ev.inline.clone() {
            let sub = Line {
                text: inline,
                no: ln.no,
                level: ln.level + 1,
                children: Vec::new(),
            };
            if let Classified::Stmt(s) = self.classify_stmt(&sub, Ctx::Actions)? {
                ev.block = vec![s];
            }
        }
        Ok(ev)
    }
}

fn attach_else(out: &mut Vec<Stmt>, body: Vec<Stmt>, ln: &Line) -> Result<(), PlainError> {
    match out.last_mut() {
        Some(Stmt::If { else_body, .. }) => {
            *else_body = body;
            Ok(())
        }
        _ => Err(PlainError::new("`otherwise` needs an `if` right above it.").at(ln.no, &ln.text)),
    }
}

fn split_colon(text: &str) -> (String, Option<String>) {
    let toks = tokenize(text);
    let mut depth: i32 = 0;
    for (i, tok) in toks.iter().enumerate() {
        match tok.kind {
            TokKind::LParen | TokKind::LBracket => depth += 1,
            TokKind::RParen | TokKind::RBracket => depth -= 1,
            TokKind::Colon if depth == 0 => {
                let right = detokenize(&toks[i + 1..]);
                return (detokenize(&toks[..i]), if right.is_empty() { None } else { Some(right) });
            }
            _ => {}
        }
    }
    (text.to_string(), None)
}

/// Index just past `"A" if cond otherwise "B"`.
fn conditional_string_end(toks: &[Tok]) -> usize {
    let mut i = 2;
    while i < toks.len() && !toks[i].is_name(&["otherwise"]) {
        i += 1;
    }
    i += 1; // past `otherwise`
    if i < toks.len() {
        i += 1;
        while toks.get(i).map(|x| x.is_op(&["."])).unwrap_or(false) && i + 1 < toks.len() {
            i += 2;
        }
    }
    i.min(toks.len())
}

fn capture_condition(toks: &[Tok], mut i: usize, params: &[String]) -> (String, usize) {
    let start = i;
    let mut depth: i32 = 0;
    while i < toks.len() {
        let t = &toks[i];
        match t.kind {
            TokKind::LParen | TokKind::LBracket => depth += 1,
            TokKind::RParen | TokKind::RBracket => depth -= 1,
            TokKind::Comma if depth == 0 => break,
            TokKind::Name if depth == 0 && t.text == "otherwise" => break,
            TokKind::Name
                if depth == 0
                    && i > start
                    && (is_value_prop1(&t.text)
                        || is_value_prop_expr(&t.text)
                        || is_special_prop(&t.text)
                        || is_flag(&t.text)
                        || t.text == "on"
                        || params.contains(&t.text)) =>
            {
                break;
            }
            _ => {}
        }
        i += 1;
    }
    (detokenize(&toks[start..i]), i)
}

fn value_tokens(toks: &[Tok], i: usize, free_expr: bool, params: &[String]) -> (String, usize) {
    if i >= toks.len() {
        return (String::new(), i);
    }
    if free_expr {
        let start = i;
        let mut i = i;
        let mut depth: i32 = 0;
        while i < toks.len() {
            let t = &toks[i];
            match t.kind {
                TokKind::LParen | TokKind::LBracket => depth += 1,
                TokKind::RParen | TokKind::RBracket => depth -= 1,
                TokKind::Comma | TokKind::Colon if depth == 0 => break,
                TokKind::Name if depth == 0 && (t.text == "if" || t.text == "otherwise") => break,
                TokKind::Name
                    if depth == 0
                        && i > start
                        && (any_prop_start(&t.text) || params.contains(&t.text)) =>
                {
                    break;
                }
                _ => {}
            }
            i += 1;
        }
        return (detokenize(&toks[start..i]), i);
    }
    let t = &toks[i];
    match t.kind {
        TokKind::Str => (format!("\"{}\"", t.text), i + 1),
        TokKind::Number | TokKind::Color => (t.text.clone(), i + 1),
        TokKind::LBracket => {
            let mut depth: i32 = 0;
            let mut j = i;
            while j < toks.len() {
                match toks[j].kind {
                    TokKind::LBracket => depth += 1,
                    TokKind::RBracket => {
                        depth -= 1;
                        if depth == 0 {
                            break;
                        }
                    }
                    _ => {}
                }
                j += 1;
            }
            let end = (j + 1).min(toks.len());
            (detokenize(&toks[i..end]), end)
        }
        _ => {
            let mut j = i + 1;
            while toks.get(j).map(|x| x.is_op(&["."])).unwrap_or(false)
                && toks.get(j + 1).map(|x| x.kind) == Some(TokKind::Name)
            {
                j += 2;
            }
            if toks.get(j).map(|x| x.kind) == Some(TokKind::LParen) {
                let mut depth: i32 = 0;
                while j < toks.len() {
                    match toks[j].kind {
                        TokKind::LParen => depth += 1,
                        TokKind::RParen => {
                            depth -= 1;
                            j += 1;
                            if depth == 0 {
                                break;
                            }
                            continue;
                        }
                        _ => {}
                    }
                    j += 1;
                }
            }
            (detokenize(&toks[i..j]), j)
        }
    }
}

fn value_prop(
    word: &str,
    toks: &[Tok],
    i: usize,
    node: &mut Node,
    params: &[String],
    free_expr: bool,
) -> usize {
    let (value, mut j) = value_tokens(toks, i + 1, free_expr, params);
    let mut prop = Prop {
        name: word.to_string(),
        value,
        condition: None,
        otherwise: None,
    };
    if toks.get(j).map(|x| x.is_name(&["if"])).unwrap_or(false) {
        let (cond, ni) = capture_condition(toks, j + 1, params);
        j = ni;
        prop.condition = Some(cond);
        if toks.get(j).map(|x| x.is_name(&["otherwise"])).unwrap_or(false) {
            j += 1;
            if toks.get(j).map(|x| x.kind) == Some(TokKind::Name) {
                let o_name = toks[j].text.clone();
                let (o_val, ni) = value_tokens(toks, j + 1, false, params);
                j = ni;
                prop.otherwise = Some(Box::new(Prop {
                    name: o_name,
                    value: o_val,
                    condition: None,
                    otherwise: None,
                }));
            }
        }
    }
    node.props.push(prop);
    j
}

fn event_from_tokens(toks: &[Tok], i: usize) -> (Event, usize) {
    let n = toks.len();
    let name = toks
        .get(i + 1)
        .map(|x| x.text.clone())
        .unwrap_or_default();
    let mut j = i + 2;
    let mut param = None;
    // binder: a Name directly before `:` (`on pinch value:`)
    if toks.get(j).map(|x| x.kind) == Some(TokKind::Name)
        && toks.get(j + 1).map(|x| x.kind) == Some(TokKind::Colon)
    {
        param = Some(toks[j].text.clone());
        j += 1;
    }
    if toks.get(j).map(|x| x.kind) == Some(TokKind::Colon) {
        let inline = detokenize(&toks[j + 1..]);
        return (
            Event {
                name,
                param,
                inline: if inline.is_empty() { None } else { Some(inline) },
                action: None,
                block: Vec::new(),
            },
            n,
        );
    }
    if toks.get(j).map(|x| x.kind) == Some(TokKind::Name) {
        let mut k = j + 1;
        if toks.get(k).map(|x| x.kind) == Some(TokKind::LParen) {
            let mut depth: i32 = 0;
            while k < n {
                match toks[k].kind {
                    TokKind::LParen => depth += 1,
                    TokKind::RParen => {
                        depth -= 1;
                        k += 1;
                        if depth == 0 {
                            break;
                        }
                        continue;
                    }
                    _ => {}
                }
                k += 1;
            }
        }
        return (
            Event {
                name,
                param,
                inline: None,
                action: Some(detokenize(&toks[j..k])),
                block: Vec::new(),
            },
            k,
        );
    }
    (
        Event {
            name,
            param,
            inline: None,
            action: None,
            block: Vec::new(),
        },
        j,
    )
}
