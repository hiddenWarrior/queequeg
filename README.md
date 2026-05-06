# Queequeg

![Queequeg logo](https://raw.githubusercontent.com/hiddenWarrior/queequeg/main/assets/logo.png)

A static analysis MCP server for Python codebases. Queequeg gives AI assistants structured code context by tracing function and class dependencies across files — so instead of opening ten files to understand one function, the assistant calls one tool and gets everything it needs.

## Why

When an AI assistant needs to understand a function, it typically reads the file, finds imports, reads those files, finds more imports, and so on. It loses context, misses things, and wastes tokens.

Queequeg does that traversal statically using AST analysis and returns a single structured result — the full dependency graph, assembled and ready to use.

## Installation

```bash
pip install queequeg
# or
uv add queequeg
```

## Setup with Claude Code

```bash
claude mcp add queequeg --scope user -- uvx --from queequeg queequeg-mcp
```

Then add a `CLAUDE.md` to your project (see [CLAUDE.md example](#claudemd-example) below) to tell Claude when and how to use it.

## Tools

### `trace_code`

Returns the full source of a symbol and all its transitive dependencies assembled into a single virtual file. Use this when you need to understand what a function actually does end-to-end.

**Example** — tracing `uses_imported_function` which calls `shared_helper` from another file:

```
# file: myproject/utils.py
def shared_helper():
    return "i am from another file"


# file: myproject/main.py
def uses_imported_function():
    return shared_helper()
```

No manual import chasing. Everything needed to understand the function is in one place.

---

### `trace_graph`

Returns a JSON dependency graph of a symbol — what it calls and what those call, recursively. Use this for a structural overview without reading all the code.

**Example:**

```json
{
  "myproject/main.py::uses_imported_function": {
    "type": "function",
    "file_path": "myproject/main.py",
    "dependencies": [
      "myproject/utils.py::shared_helper"
    ]
  },
  "myproject/utils.py::shared_helper": {
    "type": "function",
    "file_path": "myproject/utils.py",
    "dependencies": []
  }
}
```

---

### `trace_callers`

Returns a JSON graph of every function that directly or transitively calls a given symbol. The target is the root — each node lists its `callers`. Use this for impact analysis before modifying a function.

**Example** — finding everything that calls `process_user`:

```json
{
  "myproject/users.py::process_user": {
    "type": "function",
    "file_path": "myproject/users.py",
    "callers": [
      "myproject/api.py::create_user"
    ]
  },
  "myproject/api.py::create_user": {
    "type": "function",
    "file_path": "myproject/api.py",
    "callers": [
      "myproject/handlers.py::handle_request"
    ]
  },
  "myproject/handlers.py::handle_request": {
    "type": "function",
    "file_path": "myproject/handlers.py",
    "callers": []
  }
}
```

`trace_callers` accepts an optional `search_path` parameter. It defaults to the directory of the target file — pass the project root to scan the whole codebase.

---

## Limitations

- Only resolves **static** dependencies — dynamic dispatch, `getattr(obj, name)()`, callbacks stored in dicts or lists, and `__call__` are not traced
- Does not cross package boundaries — third-party library internals are not traced
- String annotations (e.g. `def foo(x: "MyModel")`) are not resolved
- `importlib.import_module()` with a dynamic string argument cannot be traced

---

## CLAUDE.md example

Add this to your project's `CLAUDE.md` to instruct Claude when to use queequeg:

```markdown
# Tools

## Queequeg MCP Tools

Use queequeg for understanding code structure, but only in specific cases:
- `mcp__queequeg__trace_code` — get the full code of a symbol and all its dependencies
- `mcp__queequeg__trace_graph` — get a structural overview of a symbol's dependency graph
- `mcp__queequeg__trace_callers` — find all functions that call a given symbol (impact analysis)

### When queequeg is useful:
- Function has dependencies scattered across **multiple different files**
- You want to pull a small relevant portion of a large file without guessing offset/limit ranges
- Understanding a deep dependency chain (e.g., function A calls B calls C calls D across different modules)
- Before modifying a function — use trace_callers to find everything that will be affected

### When queequeg is NOT useful:
- All related functions are in the **same file and nearby** (just read the file)
- Small files where reading the whole thing is faster than using a tool
- You need file context, comments, or surrounding code for understanding

### Limitations (apply to all queequeg tools):
- Only resolves **static** dependencies — dynamic dispatch, `getattr(obj, name)()`, callbacks stored in dicts or lists, and `__call__` usage will be missed
- Does not cross package boundaries — third-party library internals are not traced
- String annotations (e.g. `def foo(x: "MyModel")`) are not resolved
- `importlib.import_module()` with a dynamic string argument cannot be traced

### Special case:
If anything requires tree-sitter analysis, use queequeg — it has tree-sitter built in and can be extended for custom analysis needs.
```
