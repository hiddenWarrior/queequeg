# Harpoon — Design Document

We are following the **C4 model** for architectural design, working from the outside in:
1. **Context** — external tools and libraries we depend on
2. **Containers** — our own major components
3. **Components** — the classes and functions inside each container

---

## Level 1: Context

External dependencies:

| Library | Purpose |
|---------|---------|
| `ast` | Built-in Python parser — extracts functions, classes, and calls from source code |
| `networkx` | Graph library — represents dependency relationships between functions and classes |

---

## Level 2: Containers

| # | Container | Responsibility |
|---|-----------|---------------|
| 1 | **Parser** | Reads Python source — extracts functions, classes, globals and their dependencies |
| 2 | **Graph Builder** | Builds a graph from parsed data, stores metadata, supports topological sort and other graph algorithms |
| 3 | **JSON Serializer** | Serializes the graph into JSON (for the dependency graph feature) |
| 4 | **Code Serializer** | Serializes the graph into actual code sorted in topological order (for the virtual file feature) |
| 5 | **CLI Interface** | Entry point for humans and AI tools — easy to convert to MCP later |

---

## Level 3: Components

### Parser
| | |
|--|--|
| `load(file_path)` | Reads and parses the source file using `ast` |
| `extract_dependencies(node)` | Returns direct dependencies of a single function or class |
| `trace(function_name)` | Recursively follows all dependencies, returns a `Graph` |

### Graph
| | |
|--|--|
| `create_node(name)` | Adds a node if it doesn't already exist |
| `add_edge(from, to)` | Connects two nodes |
| `detect_cycles()` | Warns if circular dependencies are found, continues anyway |
| `topological_sort()` | Returns nodes in dependency order |
| `traverse(start_node)` | Walks the graph from a starting node, used by serializers |

### JSON Serializer
| | |
|--|--|
| `translate(graph)` | Takes a `Graph`, returns a JSON string representing the dependency graph |

### Code Serializer
| | |
|--|--|
| `translate(graph)` | Takes a `Graph`, returns code sorted in topological order as a string |

### CLI Interface
| | |
|--|--|
| `file_path.function_or_class` | Target function or class to trace |
| `--output graph \| code` | What to return — dependency graph or virtual file |
| `--mode full \| minimal` | For classes: include whole class or only what's needed |
