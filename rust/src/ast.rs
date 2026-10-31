//! AST for PL — port of the oracle's ast_nodes.py. Expressions remain
//! source text (parsed by the future expr slice) exactly as in Python.
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq)]
pub struct Line {
    pub text: String,
    pub no: usize,
    pub level: usize,
    pub children: Vec<Line>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Prop {
    pub name: String,
    pub value: String,
    pub condition: Option<String>,
    pub otherwise: Option<Box<Prop>>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Flag {
    pub name: String,
    pub condition: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Event {
    pub name: String,
    pub param: Option<String>,
    pub inline: Option<String>,
    pub action: Option<String>,
    pub block: Vec<Stmt>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Node {
    pub kind: String,
    pub line_no: usize,
    pub content: Option<String>,
    pub content_expr: Option<String>,
    pub props: Vec<Prop>,
    pub flags: Vec<Flag>,
    pub events: Vec<Event>,
    pub children: Vec<Stmt>,
    pub args: Vec<String>,
}

impl Node {
    pub fn new(kind: &str, line_no: usize) -> Self {
        Node {
            kind: kind.to_string(),
            line_no,
            content: None,
            content_expr: None,
            props: Vec::new(),
            flags: Vec::new(),
            events: Vec::new(),
            children: Vec::new(),
            args: Vec::new(),
        }
    }
    pub fn prop(&self, name: &str) -> Option<&Prop> {
        self.props.iter().find(|p| p.name == name)
    }
    pub fn has_flag(&self, name: &str) -> bool {
        self.flags.iter().any(|f| f.name == name)
    }
    pub fn event(&self, name: &str) -> Option<&Event> {
        self.events.iter().find(|e| e.name == name)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum Stmt {
    State {
        name: String,
        expr: String,
        line_no: usize,
        type_hint: Option<String>,
        shared: bool,
    },
    Derived {
        name: String,
        expr: String,
        line_no: usize,
    },
    Assign {
        target: String,
        op: String,
        expr: String,
        line_no: usize,
    },
    Action {
        name: String,
        params: Vec<String>,
        body: Vec<Stmt>,
        line_no: usize,
    },
    Resource {
        name: String,
        source: String,
        line_no: usize,
        shared: bool,
    },
    Keep {
        name: String,
        line_no: usize,
    },
    Raw {
        text: String,
        line_no: usize,
        children: Vec<Stmt>,
    },
    If {
        condition: String,
        then_body: Vec<Stmt>,
        else_body: Vec<Stmt>,
        line_no: usize,
        inline_then: Option<String>,
    },
    For {
        var: String,
        index_var: Option<String>,
        iterable: String,
        body: Vec<Stmt>,
        line_no: usize,
    },
    When {
        subject: String,
        branches: Vec<WhenBranch>,
        line_no: usize,
    },
    Node(Node),
}

impl Stmt {
    pub fn as_node(&self) -> Option<&Node> {
        match self {
            Stmt::Node(n) => Some(n),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct WhenBranch {
    pub pattern: String,
    pub body: Vec<Stmt>,
    pub line_no: usize,
}

#[derive(Debug, Clone, PartialEq)]
pub struct KindField {
    pub name: String,
    pub type_hint: Option<String>,
    pub default: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct KindDecl {
    pub name: String,
    pub fields: Vec<KindField>,
    pub line_no: usize,
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct LookDecl {
    pub name: String,
    pub props: Vec<Prop>,
    pub flags: Vec<Flag>,
    pub line_no: usize,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Component {
    pub name: String,
    pub params: Vec<String>,
    pub body: Vec<Stmt>,
    pub line_no: usize,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Page {
    pub name: String,
    pub params: Vec<String>,
    pub path: Option<String>,
    pub body: Vec<Stmt>,
    pub line_no: usize,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Capability {
    pub kind: String,
    pub target: Option<String>,
    pub line_no: usize,
    pub raw: String,
}

impl Capability {
    pub fn label(&self) -> String {
        match &self.target {
            Some(t) if !t.is_empty() => format!("{} {}", self.kind, t),
            _ => self.kind.clone(),
        }
    }
}

fn parse_http_host(url: &str) -> Result<(String, Option<u16>), String> {
    let Some((scheme_raw, rest)) = url.split_once("://") else {
        return Err(url.to_string());
    };
    let scheme = scheme_raw.to_ascii_lowercase();
    if scheme != "http" && scheme != "https" {
        return Err(format!("scheme `{scheme}`"));
    }
    let end = rest.find(&['/', '?', '#'][..]).unwrap_or(rest.len());
    let authority = &rest[..end];
    let hostport = authority
        .rsplit_once('@')
        .map_or(authority, |(_, hp)| hp);
    if hostport.is_empty() {
        return Err(url.to_string());
    }
    if hostport.starts_with('[') {
        let Some(close) = hostport.find(']') else {
            return Err(hostport.to_string());
        };
        let host = hostport[1..close].to_ascii_lowercase();
        let tail = &hostport[close + 1..];
        if tail.is_empty() {
            return Ok((host, None));
        }
        if let Some(p) = tail.strip_prefix(':') {
            return match p.parse::<u16>() {
                Ok(port) => Ok((host, Some(port))),
                Err(_) => Err(host),
            };
        }
        return Err(host);
    }
    if let Some((h, p)) = hostport.split_once(':') {
        let host = h.to_ascii_lowercase();
        if host.is_empty() {
            return Err(url.to_string());
        }
        return match p.parse::<u16>() {
            Ok(port) => Ok((host, Some(port))),
            Err(_) => Err(host),
        };
    }
    Ok((hostport.to_ascii_lowercase(), None))
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct Program {
    pub needs: Vec<String>,
    pub capabilities: Vec<Capability>,
    pub kinds: Vec<KindDecl>,
    pub components: Vec<Component>,
    pub pages: Vec<Page>,
    pub looks: Vec<LookDecl>,
    pub shared_decls: Vec<Stmt>,
    /// themes / `use` / stray top-level lines — kept for checker stages.
    pub deferred: Vec<Stmt>,
}

impl Program {
    pub fn first_page(&self) -> Option<&Page> {
        self.pages.first()
    }
    pub fn has_capability(&self, kind: &str) -> bool {
        self.capabilities.iter().any(|c| c.kind == kind)
    }
    pub fn allows_network_url(&self, url: &str) -> (bool, String) {
        let (host, port) = match parse_http_host(url) {
            Ok(v) => v,
            Err(reason) => return (false, reason),
        };
        let host_port = match port {
            Some(p) => format!("{host}:{p}"),
            None => host.clone(),
        };
        for cap in &self.capabilities {
            if cap.kind != "network" {
                continue;
            }
            let Some(raw_tgt) = &cap.target else {
                continue;
            };
            let tgt = raw_tgt.trim().to_ascii_lowercase();
            if tgt.contains(':') && !tgt.ends_with(']') {
                if tgt == host_port {
                    return (true, host_port);
                }
            } else if tgt.trim_matches(&['[', ']'][..]) == host {
                return (true, host_port);
            }
        }
        (false, host_port)
    }
    pub fn page(&self, name: &str) -> Option<&Page> {
        self.pages.iter().find(|p| p.name == name)
    }
    pub fn component(&self, name: &str) -> Option<&Component> {
        self.components.iter().find(|c| c.name == name)
    }
    pub fn kind(&self, name: &str) -> Option<&KindDecl> {
        self.kinds.iter().find(|k| k.name == name)
    }
    pub fn look(&self, name: &str) -> Option<&LookDecl> {
        self.looks.iter().find(|l| l.name == name)
    }
    pub fn page_names(&self) -> Vec<&str> {
        self.pages.iter().map(|p| p.name.as_str()).collect()
    }
    pub fn component_signatures(&self) -> BTreeMap<String, Vec<String>> {
        self.components
            .iter()
            .map(|c| (c.name.clone(), c.params.clone()))
            .collect()
    }
}
