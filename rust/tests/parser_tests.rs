//! Parity tests: the Rust port must agree with the Python oracle
//! (tests/test_stage1.py) on tokens, block tree, and classification.
use std::path::{Path, PathBuf};

use plainlang::ast::Stmt;
use plainlang::tokens::{detokenize, strip_comment, tokenize, TokKind};
use plainlang::{block_tree, parse_program};

fn examples_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../examples")
}

fn example(name: &str) -> String {
    std::fs::read_to_string(examples_dir().join(name))
        .unwrap_or_else(|e| panic!("read {name}: {e}"))
}

#[test]
fn tokenize_hyphenated_name_is_one_name() {
    let toks = tokenize("add-task sort-by");
    assert_eq!(toks.len(), 2);
    assert_eq!(toks[0].text, "add-task");
    assert_eq!(toks[0].kind, TokKind::Name);
    // subtraction needs spaces
    let toks = tokenize("a - b");
    assert_eq!(toks.len(), 3);
    assert_eq!(toks[1].text, "-");
    assert_eq!(toks[1].kind, TokKind::Op);
}

#[test]
fn hex_color_is_not_a_comment() {
    assert_eq!(
        strip_comment("x = Finish(\"Oak\", #B08968, 0)  # keep color"),
        "x = Finish(\"Oak\", #B08968, 0)"
    );
    let toks = tokenize("#5B5BD6,");
    assert_eq!(toks[0].kind, TokKind::Color);
    assert_eq!(toks[0].text, "#5B5BD6");
}

#[test]
fn detokenize_calls_and_members() {
    assert_eq!(
        detokenize(&tokenize("Task(title: draft trimmed)")),
        "Task(title: draft trimmed)"
    );
    assert_eq!(detokenize(&tokenize("task.title")), "task.title");
}

#[test]
fn bad_indent_is_a_plain_error() {
    let err = block_tree("page Home at \"/\":\n   column:\n    text \"hi\"\n")
        .expect_err("3-space indent must fail");
    assert!(err.render().contains("indented 3 spaces"), "{}", err.render());
}

#[test]
fn continuation_lines_join() {
    let prog = parse_program(
        "page Home at \"/\":\n  ok is yes\n      or no\n  column:\n    text \"x\"\n",
    )
    .unwrap();
    let page = prog.first_page().unwrap();
    match &page.body[0] {
        Stmt::Derived { name, expr, .. } => {
            assert_eq!(name, "ok");
            assert!(expr.contains("or"), "expr: {expr}");
        }
        other => panic!("expected derived, got {other:?}"),
    }
}

#[test]
fn hello_structure() {
    let prog = parse_program(&example("00-hello-world.plain")).unwrap();
    let page = prog.page("Home").expect("Home page");
    assert_eq!(page.path.as_deref(), Some("/"));
    let col = page.body.last().and_then(|s| s.as_node()).expect("column");
    assert_eq!(col.kind, "column");
    let texts: Vec<Option<String>> = col
        .children
        .iter()
        .filter_map(|s| s.as_node())
        .map(|n| n.content.clone())
        .collect();
    assert_eq!(
        texts,
        vec![
            Some("Hello, world.".to_string()),
            Some("This whole app is this file.".to_string())
        ]
    );
}

#[test]
fn button_line_is_not_an_assignment() {
    // Regression parity with the oracle: `button "−1" on tap: count -= 1`
    let prog = parse_program(&example("01-counter.plain")).unwrap();
    let comp = prog.component("Counter").expect("Counter");
    let col = comp.body.last().and_then(|s| s.as_node()).expect("column");
    let row = col
        .children
        .iter()
        .filter_map(|s| s.as_node())
        .find(|n| n.kind == "row")
        .expect("row");
    let labels: Vec<Option<String>> =
        row.children.iter().filter_map(|s| s.as_node()).map(|n| n.content.clone()).collect();
    assert_eq!(
        labels,
        vec![
            Some("−1".to_string()),
            Some("Reset".to_string()),
            Some("+1".to_string())
        ]
    );
    let plus = row.children.iter().filter_map(|s| s.as_node()).last().unwrap();
    let ev = plus.event("tap").expect("tap event");
    assert_eq!(ev.inline.as_deref(), Some("count += 1"));
}

#[test]
fn otherwise_pairs_inside_node_children() {
    let prog = parse_program(&example("02-todo.plain")).unwrap();
    let page = prog.page("Home").unwrap();
    let col = page.body.last().and_then(|s| s.as_node()).expect("column");
    let mut found = None;
    fn walk<'a>(stmts: &'a [Stmt], found: &mut Option<&'a [Stmt]>) {
        for s in stmts {
            match s {
                Stmt::If { else_body, .. } => *found = Some(else_body.as_slice()),
                Stmt::Node(n) => walk(&n.children, found),
                _ => {}
            }
        }
    }
    walk(&col.children, &mut found);
    let else_body = found.expect("an If inside the column");
    assert!(!else_body.is_empty(), "otherwise branch must be attached");
}

#[test]
fn whole_corpus_parses() {
    let mut names: Vec<PathBuf> = std::fs::read_dir(examples_dir())
        .unwrap()
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().map(|x| x == "plain").unwrap_or(false))
        .collect();
    names.sort();
    assert!(names.len() >= 9, "expected >=9 examples, got {}", names.len());
    for path in names {
        let src = std::fs::read_to_string(&path).unwrap();
        let prog = parse_program(&src)
            .unwrap_or_else(|e| panic!("{}: {}", path.display(), e.render()));
        assert!(
            !prog.pages.is_empty(),
            "{}: expected at least one page",
            path.display()
        );
    }
}
