import os
from .graph import Graph
from .symbol_indexer import SymbolIndexer
from .tracer import Tracer
from .class_reconstructor import ClassReconstructor


class Parser:
    def trace(self, file_path: str, name: str) -> Graph:
        file_path = os.path.abspath(file_path)
        source, tree = Tracer().load(file_path)
        symbols = SymbolIndexer().index(source, tree, file_path)

        if name not in symbols:
            raise ValueError(f"'{name}' not found in '{file_path}'")

        graph = Graph()
        tracer = Tracer()
        tracer.trace(file_path, name, graph, visited=set())
        ClassReconstructor().reconstruct(graph, tracer.file_cache)
        return graph
