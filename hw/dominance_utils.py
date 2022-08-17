import sys
import json
import functools

from cfg import CFG

class Dominators:
    def __init__(self, function):
        cfg = CFG(function)
        self.dom = self._compute_dominators(cfg)
        print (cfg.cfg)
        print (self.dom)

    def _compute_dominators(self, cfg):
        all_vertices = cfg.vertices
        entry_node = list(cfg.block_map.keys())[0]
        dom = {label : all_vertices for label in all_vertices}

        # entry node is dominated by entry node
        # all other nodes are initially dominated by all nodes
        dom[entry_node] = {entry_node}

        dom_changed = True
        while dom_changed:
            dom_changed = False
            for vertex in all_vertices - {entry_node}:
                vertex_predecessors = cfg.predecessors[vertex]
                pred_dominators = functools.reduce(
                        set.intersection,
                        [dom[pred] for pred in vertex_predecessors],
                        dom[vertex_predecessors[0]] if len(vertex_predecessors) > 0 else set())
                new_vertex_dom = {vertex} | pred_dominators

                if new_vertex_dom != dom[vertex]:
                    dom[vertex] = new_vertex_dom
                    dom_changed = True
                    break
        return dom

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for function in prog["functions"]:
        d = Dominators(function)
