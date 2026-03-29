import argparse
import sys
from .parser import Parser
from .serializers.code import CodeSerializer
from .serializers.json import JsonSerializer


def main():
    parser = argparse.ArgumentParser(
        description="Trace a function or class and its dependencies"
    )
    parser.add_argument("file_path", help="Path to the Python file")
    parser.add_argument("name", help="Function or class name to trace")
    parser.add_argument(
        "--output",
        choices=["code", "graph"],
        default="code",
        help="Output format: code (virtual file) or graph (dependency graph)",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "minimal"],
        default="full",
        help="For classes: include all methods (full) or only what is needed (minimal). TODO: full mode not yet implemented.",
    )

    args = parser.parse_args()

    try:
        graph = Parser().trace(args.file_path, args.name)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output == "code":
        result = CodeSerializer().translate(graph)
    else:
        result = JsonSerializer().translate(graph)

    print(result)


if __name__ == "__main__":
    main()
