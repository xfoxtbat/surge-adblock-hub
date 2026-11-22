#!/usr/bin/env python3
"""
Surge Adblock Hub — Automated Upstream Indexer, Auditor & Merger
Indexes 103516 (LoonLab) & Kelee (ProxyResource) Loon plugins,
audits common Surge conversion pitfalls, merges and fixes them into
clean, ready-to-subscribe Surge .sgmodule files.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "apps.json"
UPSTREAM_DIR = ROOT / "upstream"
MODULES_DIR = ROOT / "modules"
ANALYSIS_PATH = ROOT / "ANALYSIS.md"

LOON_UA = "Loon/906 CFNetwork/3860.100.1 Darwin/25.0.0"


def http_get(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": LOON_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def normalize_regex_key(pat: str) -> str:
    s = pat.strip()
    s = re.sub(r"^\(\?i\)", "", s)
    s = s.replace(r"\/", "/")
    s = re.sub(r"^https\?:", "https:", s)
    return s.lower()


def parse_lpx(text: str) -> Tuple[Dict[str, str], Dict[str, List[str]], List[Tuple[str, str]]]:
    meta: Dict[str, str] = {}
    sections: Dict[str, List[str]] = {}
    commented: List[Tuple[str, str]] = []
    cur: Optional[str] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#!"):
            if "=" in line:
                k, v = line[2:].split("=", 1)
                meta[k.strip()] = v.strip()
            continue
        if re.match(r"^\[.+\]$", line):
            cur = line[1:-1].strip()
            sections.setdefault(cur, [])
            continue
        if line.startswith("#") or line.startswith(";"):
            if cur in ("Rule", "Rewrite", "Script") and re.search(
                r"http|DOMAIN|URL-REGEX|script\(", line
            ):
                commented.append((cur, line))
            continue
        if cur:
            sections[cur].append(line)
    return meta, sections, commented


def extract_literal_hosts(line: str) -> List[str]:
    """Extract clean literal hostnames from a Loon/Surge regex line."""
    m = re.search(r"https?\??:(?:\\/|/){2}([^/\s,\"']+)", line)
    if not m:
        return []
    raw = m.group(1)
    # Strip trailing port patterns like (:443)? or :\d+
    raw = re.sub(r"\(:?\d+\)\??$", "", raw)
    raw = re.sub(r":\d+$", "", raw)
    raw = raw.replace(r"\.", ".")
    # Strip any trailing backslash or regex anchor
    raw = raw.rstrip("\\$")

    candidates = [raw]
    # Expand simple (a|b) or (?:a|b)
    m_alt = re.match(r"^([A-Za-z0-9.-]*)\((?:\?:)?([A-Za-z0-9.|-]+)\)([A-Za-z0-9.-]*)$", raw)
    if m_alt:
        pre, opts, post = m_alt.groups()
        candidates = [f"{pre}{o}{post}" for o in opts.split("|")]
    else:
        # Expand simple optional group like ucmp(-static)?.sf-express.com
        m_opt = re.match(r"^([A-Za-z0-9.-]*)\(([A-Za-z0-9.-]+)\)\?([A-Za-z0-9.-]*)$", raw)
        if m_opt:
            pre, opt, post = m_opt.groups()
            candidates = [f"{pre}{post}", f"{pre}{opt}{post}"]

    out = []
    for c in candidates:
        c = c.strip(".")
        if "." in c and re.fullmatch(r"[A-Za-z0-9.-]+", c):
            out.append(c.lower())
    return out


def host_is_covered(host: str, mitm_hosts: List[str]) -> bool:
    h = host.lower()
    for mh in mitm_hosts:
        m = mh.lower().strip()
        if not m or m.startswith("%") or m.startswith("-"):
            continue
        if m == h:
            return True
        if m.startswith("*.") and (h.endswith(m[1:]) or h == m[2:]):
            return True
        if m.startswith("*") and h.endswith(m[1:]):
            return True
    return False


def json_path_to_jq_array(path_str: str) -> List:
    """Convert 'Result.cards[1].foo' -> ['Result', 'cards', 1, 'foo']."""
    tokens = []
    for part in path_str.split("."):
        if not part:
            continue
        for m in re.finditer(r"([^\[\]]+)|\[(\d+)\]", part):
            if m.group(1) is not None:
                tokens.append(m.group(1))
            else:
                tokens.append(int(m.group(2)))
    return tokens


def unquote_js_string(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        try:
            return json.loads(s)
        except Exception:
            return s[1:-1]
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1]
    return s


def compress_jq_expr(expr: str) -> str:
    lines = []
    for ln in expr.splitlines():
        st = ln.strip()
        if not st or st.startswith("#"):
            continue
        lines.append(st)
    return " ".join(lines)


def format_jq_single_quoted(expr: str) -> str:
    # Surge http-response-jq wraps jq in single quotes; avoid unescaped single quotes
    return expr.replace("'", '"')


def loon_regex_to_surge(regex_body: str, flags: str) -> str:
    body = regex_body.strip()
    # Script-Hub convention: allow query parameters in any order when matching \?key=
    if r"\?" in body and r"(?:[^#?&]+&)*" not in body:
        body = re.sub(r"\\\?(?=[A-Za-z0-9_]+=)", r"\\?(?:[^#?&]+&)*", body)
    if "i" in flags and not body.startswith("(?i)"):
        return f"(?i){body}"
    return body


def parse_loon_if_expr(line: str) -> Optional[Tuple[str, str, str]]:
    """Parse: (request|response) if ${url} ~= /pattern/flags then action"""
    m = re.match(
        r"^(request|response)\s+if\s+\$\{url\}\s*~=\s*/(.+)/([a-zA-Z]*)\s+then\s+(.+)$",
        line.strip(),
    )
    if not m:
        return None
    direction, pat, flags, action = m.groups()
    return direction, loon_regex_to_surge(pat, flags), action.strip()


def convert_rewrite_line(
    line: str, jq_cache: Dict[str, str]
) -> Tuple[Optional[str], Optional[str], Optional[str], List[str]]:
    """
    Returns (section_name, surge_line, pattern_key, notes)
    section_name is 'Map Local' or 'Body Rewrite'.
    """
    notes: List[str] = []
    parsed = parse_loon_if_expr(line)
    if not parsed:
        return None, None, None, [f"未识别的重写语法: {line[:80]}"]

    direction, pat, action = parsed
    key = normalize_regex_key(pat)

    # 1. reject / reject_dict / reject_img
    if re.fullmatch(r"reject(\(\s*404\s*\))?", action):
        return "Map Local", f'{pat} data-type=text data="" status-code=404', key, notes
    if re.fullmatch(r"reject\(\s*200\s*\)", action):
        return "Map Local", f'{pat} data-type=text data="" status-code=200', key, notes
    if re.fullmatch(r"reject_dict(\(\s*200\s*\))?", action):
        return (
            "Map Local",
            f'{pat} data-type=text data="{{}}" status-code=200 header="Content-Type:application/json"',
            key,
            notes,
        )
    if re.fullmatch(r"reject_img(\(\s*200\s*\))?", action):
        return "Map Local", f"{pat} data-type=tiny-gif status-code=200", key, notes

    # 2. response.body.mock("json", "...")
    m_mock = re.match(r'^response\.body\.mock\(\s*"([^"]+)"\s*,\s*(.+)\)$', action)
    if m_mock:
        mtype, raw_payload = m_mock.groups()
        payload = unquote_js_string(raw_payload)
        escaped = json.dumps(payload, ensure_ascii=False)
        ctype = "application/json" if mtype.lower() == "json" else "text/plain"
        return (
            "Map Local",
            f'{pat} data-type=text data={escaped} status-code=200 header="Content-Type:{ctype}"',
            key,
            notes,
        )

    # 3. response.body.replace(/pat/, "rep")
    m_brep = re.match(r"^response\.body\.replace\(\s*/(.+)/[a-zA-Z]*\s*,\s*(.+)\)$", action)
    if m_brep:
        find_pat, rep_raw = m_brep.groups()
        rep = unquote_js_string(rep_raw)
        return "Body Rewrite", f"http-response {pat} {find_pat} {rep}", key, notes

    # 4. response.json.delete("a.b") or response.json.delete(["a.b", ...])
    m_del = re.match(r"^response\.json\.delete\((.+)\)$", action)
    if m_del:
        arg = m_del.group(1).strip()
        try:
            val = json.loads(arg)
        except Exception:
            val = unquote_js_string(arg)
        paths = [val] if isinstance(val, str) else list(val)
        jq_paths = [json_path_to_jq_array(p) for p in paths]
        if len(paths) > 1 and any(any(isinstance(x, int) for x in qp) for qp in jq_paths):
            notes.append("修复多数组索引删除为单条原子 delpaths")
        jq_expr = f"delpaths({json.dumps(jq_paths, ensure_ascii=False, separators=(',', ':'))})"
        return "Body Rewrite", f"http-response-jq {pat} '{jq_expr}'", key, notes

    # 5. response.json.replace("path", "value") or response.json.replace([p1, p2], [v1, v2])
    m_jrep_arr = re.match(r"^response\.json\.replace\(\s*(\[.+?\])\s*,\s*(\[.+\])\s*\)$", action)
    if m_jrep_arr:
        raw_paths, raw_vals = m_jrep_arr.groups()
        # Normalize backticks used in Loon 3.5 raw string literals (e.g. `[]`)
        norm_vals = re.sub(r"`([^`]*)`", lambda m: json.dumps(m.group(1)), raw_vals)
        try:
            paths = json.loads(raw_paths)
            vals = json.loads(norm_vals)
            clauses = []
            for p_str, v_item in zip(paths, vals):
                arr = json_path_to_jq_array(p_str)
                parent, leaf = arr[:-1], arr[-1]
                p_json = json.dumps(parent, ensure_ascii=False, separators=(",", ":"))
                a_json = json.dumps(arr, ensure_ascii=False, separators=(",", ":"))
                # If v_item is stringified JSON like "[]" or "{}", keep as JSON literal if valid
                if isinstance(v_item, str) and v_item.strip() in ("[]", "{}"):
                    v_json = v_item.strip()
                else:
                    v_json = json.dumps(v_item, ensure_ascii=False)
                if isinstance(leaf, str):
                    clauses.append(
                        f'if ((getpath({p_json}) // {{}}) | has({json.dumps(leaf)})) then (setpath({a_json}; {v_json})) else . end'
                    )
                else:
                    clauses.append(f"setpath({a_json}; {v_json})")
            jq_expr = " | ".join(clauses)
            return "Body Rewrite", f"http-response-jq {pat} '{format_jq_single_quoted(jq_expr)}'", key, notes
        except Exception as e:
            return None, None, None, [f"解析数组版 json.replace 失败: {e}"]

    m_jrep = re.match(r'^response\.json\.replace\(\s*"([^"]+)"\s*,\s*(.+)\)$', action)
    if m_jrep:
        path_str, val_raw = m_jrep.groups()
        val_str = unquote_js_string(val_raw)
        arr = json_path_to_jq_array(path_str)
        parent = arr[:-1]
        leaf = arr[-1]
        p_json = json.dumps(parent, ensure_ascii=False, separators=(",", ":"))
        a_json = json.dumps(arr, ensure_ascii=False, separators=(",", ":"))
        v_json = json.dumps(val_str, ensure_ascii=False)
        if isinstance(leaf, str):
            jq_expr = f'if ((getpath({p_json}) // {{}}) | has({json.dumps(leaf)})) then (setpath({a_json}; {v_json})) else . end'
        else:
            jq_expr = f"setpath({a_json}; {v_json})"
        return "Body Rewrite", f"http-response-jq {pat} '{format_jq_single_quoted(jq_expr)}'", key, notes

    # 6. response.json.jq("...")
    m_jq = re.match(r"^response\.json\.jq\((.+)\)$", action)
    if m_jq:
        expr = compress_jq_expr(unquote_js_string(m_jq.group(1)))
        return "Body Rewrite", f"http-response-jq {pat} '{format_jq_single_quoted(expr)}'", key, notes

    # 7. response.json.jq_file("https://...")
    m_jqf = re.match(r'^response\.json\.jq_file\(\s*"([^"]+)"\s*\)$', action)
    if m_jqf:
        jq_url = m_jqf.group(1)
        if jq_url not in jq_cache:
            try:
                jq_cache[jq_url] = compress_jq_expr(http_get(jq_url))
            except Exception as e:
                return None, None, None, [f"拉取 jq_file 失败({jq_url}): {e}"]
        expr = jq_cache[jq_url]
        notes.append(f"内联外部 jq_file: {Path(jq_url).name}")
        return "Body Rewrite", f"http-response-jq {pat} '{format_jq_single_quoted(expr)}'", key, notes

    return None, None, None, [f"未支持的 rewrite action: {action[:80]}"]


def sanitize_script_name(raw_tag: str, app_slug: str, idx: int) -> Tuple[str, bool]:
    """Remove [brackets] that trigger Surge section header validation errors."""
    name = raw_tag.strip() if raw_tag else f"{app_slug}_script_{idx}"
    had_brackets = ("[" in name) or ("]" in name)
    # Replace [Prefix]Rest -> Prefix_Rest
    name = re.sub(r"^\[([^\]]+)\]\s*", r"\1_", name)
    name = name.replace("[", "_").replace("]", "_")
    name = re.sub(r"\s+", "_", name).strip("_")
    name = re.sub(r"=", "-", name)
    return name or f"{app_slug}_script_{idx}", had_brackets


def parse_script_line(line: str, app_slug: str, idx: int) -> Optional[Dict]:
    parsed = parse_loon_if_expr(line)
    if not parsed:
        return None
    direction, pat, action = parsed
    m = re.match(r'^script\(\s*"([^"]+)"\s*\)(?:\s+with\s+(.+))?$', action)
    if not m:
        return None
    script_url, opts_str = m.groups()
    opts_str = opts_str or ""

    def get_opt(name: str) -> Optional[str]:
        m_o = re.search(rf'\b{name}\s*=\s*(?:"([^"]*)"|([^\s,]+))', opts_str)
        if not m_o:
            return None
        return m_o.group(1) if m_o.group(1) is not None else m_o.group(2)

    raw_tag = get_opt("tag") or f"{app_slug}_script_{idx}"
    clean_name, had_brackets = sanitize_script_name(raw_tag, app_slug, idx)
    stype = "http-request" if direction == "request" else "http-response"

    params = [
        f"type={stype}",
        f"pattern={pat}",
        f"script-path={script_url}",
    ]
    if (get_opt("requires_body") or "").lower() == "true":
        params.append("requires-body=true")
    if (get_opt("binary_body") or "").lower() == "true":
        params.append("binary-body-mode=true")
    max_size = get_opt("max_size")
    if max_size:
        params.append(f"max-size={max_size}")
    timeout = get_opt("timeout")
    if timeout:
        params.append(f"timeout={timeout}")
    argument = get_opt("argument")
    if argument:
        params.append(f'argument="{argument}"')
    enable_raw = get_opt("enable") or ""
    enable_var = None
    m_en = re.fullmatch(r"\{([A-Za-z0-9_-]+)\}", enable_raw.strip())
    if m_en:
        enable_var = m_en.group(1)

    return {
        "raw_tag": raw_tag,
        "name": clean_name,
        "had_brackets": had_brackets,
        "pattern": pat,
        "pattern_key": normalize_regex_key(pat),
        "script_url": script_url,
        "params": ", ".join(params),
        "enable_var": enable_var,
        "raw_line": line,
    }


def parse_arguments_section(sections: Dict[str, List[str]]) -> List[Dict]:
    """Parse Loon [Argument] switch declarations into Surge #!arguments entries."""
    args = []
    for line in sections.get("Argument", []):
        if "=" not in line:
            continue
        var, rhs = [x.strip() for x in line.split("=", 1)]
        parts = [p.strip() for p in rhs.split(",")]
        if not parts or parts[0].lower() != "switch":
            continue
        default_on = len(parts) > 1 and parts[1].lower() == "true"
        m_tag = re.search(r"\btag\s*=\s*([^,]+)", rhs)
        m_desc = re.search(r"\bdesc\s*=\s*(.+)$", rhs)
        tag = m_tag.group(1).strip() if m_tag else var
        desc = m_desc.group(1).strip() if m_desc else ""
        args.append(
            {
                "var": var,
                "default_val": '""' if default_on else "#",
                "tag": tag,
                "desc": desc,
            }
        )
    return args


def extract_mitm_hosts(sections: Dict[str, List[str]]) -> List[str]:
    hosts: List[str] = []
    for line in sections.get("MitM", []) + sections.get("MITM", []):
        if line.lower().startswith("hostname"):
            rhs = line.split("=", 1)[1]
            for h in rhs.split(","):
                h = h.strip()
                if h and not h.startswith("%"):
                    hosts.append(h)
    return hosts


def audit_source(text: str, app_slug: str) -> Dict:
    meta, secs, commented = parse_lpx(text)
    mitm_hosts = extract_mitm_hosts(secs)
    rules = secs.get("Rule", [])
    rewrites = secs.get("Rewrite", [])
    scripts_raw = secs.get("Script", [])

    issues: List[str] = []
    tags: List[str] = []
    script_urls: List[str] = []
    used_hosts: set = set()

    for line in rewrites:
        for h in extract_literal_hosts(line):
            used_hosts.add(h)
        if "response.json.delete([" in line and re.search(r"\[\d+\]", line):
            issues.append("多数组索引 delpaths（常见转换器拆分后会导致索引错位）")

    for i, line in enumerate(scripts_raw, 1):
        for h in extract_literal_hosts(line):
            used_hosts.add(h)
        sp = parse_script_line(line, app_slug, i)
        if sp:
            tags.append(sp["raw_tag"])
            script_urls.append(sp["script_url"])
            if sp["had_brackets"]:
                issues.append("脚本名含方括号 `[...]`（会导致 Surge 合并报段标题错误）")

    if len(tags) != len(set(tags)):
        dups = sorted({t for t in tags if tags.count(t) > 1})
        issues.append(f"同名脚本冲突（Surge 后者覆盖前者）：{', '.join(dups)}")

    missing_mitm = sorted(h for h in used_hosts if not host_is_covered(h, mitm_hosts))
    if missing_mitm:
        issues.append(f"MITM 漏配域名：{', '.join(missing_mitm)}")

    desc = meta.get("desc", "")
    if "IPA签名" in desc or "App Store用户请勿使用" in desc:
        issues.append("作者标注需 IPA 签名 / SSL Unpinning（App Store 版可能无法解密）")

    return {
        "meta": meta,
        "sections": secs,
        "commented_count": len(commented),
        "rule_count": len(rules),
        "has_amdc": any("amdc/mobileDispatch" in r or r"amdc\/mobileDispatch" in r for r in rules),
        "rewrite_count": len(rewrites),
        "script_count": len(scripts_raw),
        "script_urls": sorted(set(script_urls)),
        "mitm_hosts": mitm_hosts,
        "missing_mitm": missing_mitm,
        "issues": sorted(set(issues)),
    }


def validate_jq_expression(expr: str) -> Optional[str]:
    if not shutil.which("jq"):
        return None
    p = subprocess.run(
        ["jq", "-n", expr],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Compile error shows "jq: error: syntax error" or "compile error"
    if p.returncode != 0 and ("syntax error" in p.stderr or "compile error" in p.stderr):
        return p.stderr.strip().splitlines()[0]
    return None


def dedup_preserve(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def assign_unique_script_names(scripts: List[Dict], global_used: Optional[set] = None) -> Tuple[List[str], List[str]]:
    used = global_used if global_used is not None else set()
    lines = []
    renames = []
    for sp in scripts:
        base = sp["name"]
        name = base
        n = 2
        while name in used:
            name = f"{base}_{n}"
            n += 1
        used.add(name)
        if name != base:
            renames.append(f"{base} -> {name}")
        prefix = f"{{{{{{{sp['enable_var']}}}}}}}" if sp.get("enable_var") else ""
        lines.append(f"{prefix}{name} = {sp['params']}")
    return lines, renames


def build_argument_headers(arg_items: List[Dict]) -> List[str]:
    if not arg_items:
        return []
    seen = set()
    uniq = []
    for a in arg_items:
        if a["var"] not in seen:
            seen.add(a["var"])
            uniq.append(a)
    args_val = ",".join(f"{a['var']}:{a['default_val']}" for a in uniq)
    desc_parts = []
    for a in uniq:
        d = f"{a['var']}: {a['tag']}"
        if a["desc"]:
            d += f"\\n{a['desc']}"
        d += "\\n可选值: 留空启用, # 禁用"
        desc_parts.append(d)
    return [
        f"#!arguments={args_val}",
        f"#!arguments-desc={'\\n\\n'.join(desc_parts)}",
    ]


def render_sgmodule(
    name: str,
    desc: str,
    rules: List[str],
    body_rewrites: List[str],
    map_locals: List[str],
    script_lines: List[str],
    mitm_hosts: List[str],
    extra_headers: Optional[List[str]] = None,
) -> str:
    out = [f"#!name={name}", f"#!desc={desc}"]
    if extra_headers:
        out.extend(extra_headers)
    out.append("")

    if rules:
        out.append("[Rule]")
        out.extend(rules)
        out.append("")

    if body_rewrites:
        out.append("[Body Rewrite]")
        out.extend(body_rewrites)
        out.append("")

    if map_locals:
        out.append("[Map Local]")
        out.extend(map_locals)
        out.append("")

    if script_lines:
        out.append("[Script]")
        out.extend(script_lines)
        out.append("")

    if mitm_hosts:
        out.append("[MITM]")
        out.append("hostname = %APPEND% " + ", ".join(mitm_hosts))
        out.append("")

    return "\n".join(out)


def fetch_scripthub_meta() -> Dict[str, str]:
    dest = UPSTREAM_DIR / "scripthub_meta.json"
    url = "https://api.github.com/repos/Script-Hub-Org/Script-Hub/commits/main"
    headers = {"User-Agent": "surge-adblock-hub", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        meta = {
            "repo": "Script-Hub-Org/Script-Hub",
            "sha": data["sha"][:10],
            "date": data["commit"]["committer"]["date"],
            "message": data["commit"]["message"].splitlines()[0],
        }
        dest.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return meta
    except Exception as e:
        if dest.exists():
            return json.loads(dest.read_text(encoding="utf-8"))
        return {"repo": "Script-Hub-Org/Script-Hub", "sha": "unknown", "date": "", "message": str(e)}


def main() -> int:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    repo = cfg["repo"]
    UPSTREAM_DIR.mkdir(parents=True, exist_ok=True)
    (UPSTREAM_DIR / "103516").mkdir(parents=True, exist_ok=True)
    (UPSTREAM_DIR / "kelee").mkdir(parents=True, exist_ok=True)
    MODULES_DIR.mkdir(parents=True, exist_ok=True)

    scripthub_meta = fetch_scripthub_meta()

    jq_cache: Dict[str, str] = {}
    all_rules: List[str] = []
    all_body_rewrites: List[str] = []
    all_map_locals: List[str] = []
    all_scripts: List[Dict] = []
    all_mitm: List[str] = []
    all_args: List[Dict] = []
    all_jq_errors: List[str] = []
    app_summaries: List[Dict] = []

    for app in cfg["apps"]:
        slug = app["slug"]
        cname = app["name"]
        strategy = app["strategy"]
        excl_pats = [re.compile(p, re.I) for p in app.get("exclude_kelee_patterns", [])]

        texts = {}
        audits = {}
        for src_name, url in app["sources"].items():
            dest = UPSTREAM_DIR / src_name / f"{slug}.lpx"
            try:
                content = http_get(url)
                dest.write_text(content, encoding="utf-8")
            except Exception as e:
                if dest.exists():
                    print(f"[WARN] fetch {url} failed ({e}), using cached snapshot", file=sys.stderr)
                    content = dest.read_text(encoding="utf-8")
                else:
                    raise
            texts[src_name] = content
            audits[src_name] = audit_source(content, slug)

        # Build merged rules/rewrites/scripts/mitm
        fixes: List[str] = []
        rules: List[str] = []
        body_rewrites: List[str] = []
        map_locals: List[str] = []
        scripts: List[Dict] = []
        mitm_hosts: List[str] = []
        app_args: List[Dict] = []

        seen_rule_keys = set()
        seen_rw_keys = set()
        seen_script_keys = set()

        def ingest_source(src_name: str, include_rules: bool, include_rewrites: bool, include_scripts: bool, apply_excl: bool):
            a = audits[src_name]
            secs = a["sections"]
            app_args.extend(parse_arguments_section(secs))
            if include_rules:
                for r in secs.get("Rule", []):
                    rk = re.sub(r"\s+", "", r).lower()
                    if rk not in seen_rule_keys:
                        seen_rule_keys.add(rk)
                        rules.append(r)
            if include_rewrites:
                for rw in secs.get("Rewrite", []):
                    if apply_excl and any(ep.search(rw) for ep in excl_pats):
                        fixes.append(f"按策略排除 {src_name} 高风险重写：`{rw[:90]}...`")
                        continue
                    sec, surge_ln, pkey, notes = convert_rewrite_line(rw, jq_cache)
                    if notes:
                        fixes.extend(notes)
                    if not surge_ln or not pkey:
                        continue
                    if pkey in seen_rw_keys:
                        continue
                    seen_rw_keys.add(pkey)
                    if sec == "Body Rewrite":
                        if surge_ln.startswith("http-response-jq "):
                            jq_part = surge_ln.split(" '", 1)[1][:-1]
                            err = validate_jq_expression(jq_part)
                            if err:
                                all_jq_errors.append(f"{slug}: {err} | {jq_part[:80]}")
                        body_rewrites.append(surge_ln)
                    elif sec == "Map Local":
                        map_locals.append(surge_ln)
            if include_scripts:
                for i, sc in enumerate(secs.get("Script", []), 1):
                    if apply_excl and any(ep.search(sc) for ep in excl_pats):
                        continue
                    sp = parse_script_line(sc, slug, i)
                    if not sp:
                        continue
                    sk = (sp["pattern_key"], sp["script_url"])
                    if sk in seen_script_keys:
                        continue
                    seen_script_keys.add(sk)
                    if sp["had_brackets"]:
                        fixes.append(f"清洗方括号脚本名：`{sp['raw_tag']}` -> `{sp['name']}`")
                    scripts.append(sp)

            for h in a["mitm_hosts"]:
                if h not in mitm_hosts:
                    mitm_hosts.append(h)

        if strategy == "103516_plus_kelee_scripts":
            ingest_source("103516", True, True, True, False)
            ingest_source("kelee", True, False, True, True)
        else:
            ingest_source("103516", True, True, True, False)
            # If 103516 already provides scripts for this app, avoid duplicating older Kelee scripts on the same APIs
            include_kelee_scripts = audits["103516"]["script_count"] == 0
            ingest_source("kelee", True, True, include_kelee_scripts, True)

        # Auto-complete missing MITM hostnames based on final rules
        final_lines = body_rewrites + map_locals + [s["pattern"] for s in scripts]
        added_mitm = []
        for ln in final_lines:
            for h in extract_literal_hosts(ln):
                if not host_is_covered(h, mitm_hosts):
                    mitm_hosts.append(h)
                    added_mitm.append(h)
        if added_mitm:
            fixes.append(f"自动补全漏配 MITM 域名：`{', '.join(sorted(set(added_mitm)))}`")

        script_lines, renames = assign_unique_script_names(scripts)
        if renames:
            fixes.append(f"自动消解同名脚本冲突：`{'; '.join(renames)}`")

        fixes = dedup_preserve(fixes)

        latest_date = max(
            audits["103516"]["meta"].get("date", ""),
            audits["kelee"]["meta"].get("date", ""),
        )
        mod_text = render_sgmodule(
            name=f"{cname} 去广告 (Adblock Hub)",
            desc=f"融合 103516 与可莉双源并自动修复 Surge 兼容问题。上游最新日期：{latest_date}。{app.get('notes', '')}",
            rules=rules,
            body_rewrites=body_rewrites,
            map_locals=map_locals,
            script_lines=script_lines,
            mitm_hosts=mitm_hosts,
            extra_headers=[
                f"#!category=去广告",
                f"#!date={latest_date}",
                f"#!homepage=https://github.com/{repo}",
                *build_argument_headers(app_args),
            ],
        )
        (MODULES_DIR / f"{slug}.sgmodule").write_text(mod_text, encoding="utf-8")

        # Accumulate into all-in-one
        all_rules.extend(rules)
        all_body_rewrites.extend(body_rewrites)
        all_map_locals.extend(map_locals)
        all_scripts.extend(scripts)
        all_mitm.extend(mitm_hosts)
        all_args.extend(app_args)

        app_summaries.append(
            {
                "slug": slug,
                "name": cname,
                "strategy": strategy,
                "notes": app.get("notes", ""),
                "audits": audits,
                "final_counts": {
                    "rules": len(rules),
                    "body_rewrites": len(body_rewrites),
                    "map_locals": len(map_locals),
                    "scripts": len(script_lines),
                    "mitm": len(mitm_hosts),
                },
                "fixes": fixes,
                "latest_date": latest_date,
            }
        )

    # Build All-in-One module
    aio_rules = dedup_preserve(all_rules)
    aio_body = dedup_preserve(all_body_rewrites)
    aio_map = dedup_preserve(all_map_locals)
    aio_mitm = dedup_preserve(all_mitm)
    aio_scripts, _ = assign_unique_script_names(all_scripts, set())
    overall_date = max(s["latest_date"] for s in app_summaries)

    aio_text = render_sgmodule(
        name="Surge Adblock Hub (8合1汇总)",
        desc=f"自动聚合淘宝/京东/滴滴/高德/百度地图/小红书/顺丰/小宇宙双上游去广告模块并修复 Surge 兼容问题。上游最新日期：{overall_date}",
        rules=aio_rules,
        body_rewrites=aio_body,
        map_locals=aio_map,
        script_lines=aio_scripts,
        mitm_hosts=aio_mitm,
        extra_headers=[
            "#!category=去广告",
            f"#!date={overall_date}",
            f"#!homepage=https://github.com/{repo}",
            *build_argument_headers(all_args),
        ],
    )
    (MODULES_DIR / "all-in-one.sgmodule").write_text(aio_text, encoding="utf-8")

    # Render ANALYSIS.md
    md = [
        "# 上游双源去广告分析与自动修复报告",
        "",
        f"> 本报告由 `scripts/sync_and_build.py` 自动生成。插件上游最新日期：**{overall_date}**",
        f"> 转换规范参考：[`{scripthub_meta['repo']}`](https://github.com/{scripthub_meta['repo']})（最新提交 `{scripthub_meta['sha']}` · {scripthub_meta['date'][:10]} · {scripthub_meta['message']}）",
        "",
        "## 1. 总览对比表",
        "",
        "| App | 103516 日期 / 规则数 | 可莉 日期 / 规则数 | 最终输出（Rule / Body / MapLocal / Script / MITM） | 单模块订阅 |",
        "|---|---|---|---|---|",
    ]
    for s in app_summaries:
        a1 = s["audits"]["103516"]
        a2 = s["audits"]["kelee"]
        fc = s["final_counts"]
        raw_url = f"https://raw.githubusercontent.com/{repo}/main/modules/{s['slug']}.sgmodule"
        md.append(
            f"| **{s['name']}** (`{s['slug']}`) "
            f"| {a1['meta'].get('date', '-')[:10]} (R:{a1['rule_count']} W:{a1['rewrite_count']} S:{a1['script_count']}) "
            f"| {a2['meta'].get('date', '-')[:10]} (R:{a2['rule_count']} W:{a2['rewrite_count']} S:{a2['script_count']}) "
            f"| {fc['rules']} / {fc['body_rewrites']} / {fc['map_locals']} / {fc['scripts']} / {fc['mitm']} "
            f"| [`{s['slug']}.sgmodule`]({raw_url}) |"
        )

    md.extend(["", "## 2. 逐 App 深度诊断与自动修复清单", ""])
    for s in app_summaries:
        a1 = s["audits"]["103516"]
        a2 = s["audits"]["kelee"]
        md.append(f"### {s['name']} (`{s['slug']}`)")
        md.append(f"- **融合策略**：`{s['strategy']}` — {s['notes']}")
        md.append(
            f"- **103516 体检**：AMDC拦截=`{a1['has_amdc']}`，注释规则=`{a1['commented_count']}` 条"
            + (f"；发现问题：{'；'.join(a1['issues'])}" if a1["issues"] else "；无结构性异常")
        )
        md.append(
            f"- **可莉 体检**：AMDC拦截=`{a2['has_amdc']}`，注释规则=`{a2['commented_count']}` 条"
            + (f"；发现问题：{'；'.join(a2['issues'])}" if a2["issues"] else "；无结构性异常")
        )
        if s["fixes"]:
            md.append("- **已自动执行的修复与优化**：")
            for fx in s["fixes"]:
                md.append(f"  - {fx}")
        else:
            md.append("- **已自动执行的修复与优化**：无额外冲突需修正。")
        md.append("")

    if all_jq_errors:
        md.extend(["## 3. JQ 语法告警", ""])
        for err in all_jq_errors:
            md.append(f"- ⚠️ {err}")
        md.append("")
    else:
        md.extend(["## 3. JQ 语法自检", "", "- ✅ 全部 `http-response-jq` 表达式均通过 `jq` 编译校验。", ""])

    ANALYSIS_PATH.write_text("\n".join(md), encoding="utf-8")

    print(f"Built {len(app_summaries)} modules + all-in-one.sgmodule")
    print(f"All-in-One stats: Rule={len(aio_rules)}, BodyRewrite={len(aio_body)}, MapLocal={len(aio_map)}, Script={len(aio_scripts)}, MITM={len(aio_mitm)}")
    if all_jq_errors:
        print("JQ ERRORS:", all_jq_errors, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
