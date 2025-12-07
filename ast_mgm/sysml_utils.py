import jpype
import json
from graphviz import Digraph
from zss import Node, distance
from graphviz import Digraph
from IPython.display import Image, display, SVG

class SysMLASTManager():
    def __init__(self):

        # Use this command in terminal to compile SysMLParserService.java if updated
        # # javac -cp ".;java_dependencies/*" SysMLParserService.java

        # Start the Java Virtual Machine (JVM) and point to the requires .jar and .class files
        if not jpype.isJVMStarted():
            jpype.startJVM(classpath=[".","java_dependencies/*"])

        # Import the parser class. Can take several minutes as it loads all library dependencies
        self.parser = jpype.JClass("SysMLParserService")
    
    def code_to_ast(self, sysml_code):
        try:
            ast_json = self.parser.parseString(sysml_code)
            ast = json.loads(str(ast_json))
            return ast
        except jpype.JException as e:
            error = str(e)
            if "ParseException" in error:
                return error 
            else:
                raise
    
    def _add_nodes_edges(self, graph, node, parent=None):
        node_id = str(id(node))
        label = node.get("type", "?")
        if "name" in node:
            label += f"\n{node['name']}"
        graph.node(node_id, label)
        if parent:
            graph.edge(parent, node_id)
        for child in node.get("children", []):
            self._add_nodes_edges(graph, child, node_id)

    def visualize_ast(self, ast, filename="ast_diagram", display_inline=True, format="png"):
        g = Digraph(comment="SysML AST", format=format)
        self._add_nodes_edges(g, ast)

        if display_inline:
            if format == "svg":
                display(SVG(g.pipe(format="svg")))
            else:
                display(Image(g.pipe(format=format)))
        else:
            output_path = g.render(filename, view=False)
            print(f"Graph saved to {output_path}")
    
    def _dict_to_node(self, d, depth=0):
        n = Node((d.get("type", ""), depth))
        for c in d.get("children", []):
            n.addkid(self._dict_to_node(c, depth + 1))
        return n

    def _insert_cost(self, n):
        _, depth = n.label
        return 1 / (1 + depth)

    def _remove_cost(self, n):
        _, depth = n.label
        return 1 / (1 + depth)

    def _update_cost(self, a, b):
        (atype, adepth), (btype, bdepth) = a.label, b.label

        atype, *aname = atype.split(":", 1)
        btype, *bname = btype.split(":", 1)
        aname = aname[0] if aname else ""
        bname = bname[0] if bname else ""

        if atype != btype:
            # Structural change — big penalty
            return 1.0 / (1 + min(adepth, bdepth))
        elif aname != bname:
            # Rename only — minor penalty
            return 0.05 / (1 + min(adepth, bdepth))
        else:
            return 0.0

    def compare_asts(self, ast1: dict, ast2: dict) -> float:
        tree1 = self._dict_to_node(ast1)
        tree2 = self._dict_to_node(ast2)
        
        dist = distance(
            tree1, 
            tree2,
            get_children=lambda n: n.children,
            insert_cost=self._insert_cost,
            remove_cost=self._remove_cost,
            update_cost=self._update_cost
        )
        
        return 1 / (1 + dist)