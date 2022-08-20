import sys
import json
import functools
import collections

from cfg import CFG

class Dominators:
    def __init__(self, function):
        cfg = CFG(function)
        self.dom = self._compute_dominators(cfg)
        self.dominance_tree = self._compute_dominance_tree()
        print (cfg.cfg)
        print (self.dom)
        print (self.dominance_tree)

    def _compute_dominance_tree(self):
        tree = {parent: [] for parent in self.dom.keys()}

        # optimization, sort paths and insert into dict where key is length
        tree_paths = {}
        for sorted_paths in sorted(self.dom.values(), key=lambda x: len(x)):
            path_length = len(sorted_paths)
            tree_paths.setdefault(path_length, []).append(sorted_paths)

        root = tree_paths[1][0]
        root_node, = root
        Q = collections.deque()
        Q.append((root, root_node))

        while len(Q) > 0:
            parent_path, parent_node = Q.popleft()

            if len(parent_path) + 1 not in tree_paths:
                break

            # find all child nodes of v
            for child_path in tree_paths[len(parent_path) + 1]:
                # maybe this is a child node from some other node, don't do anything
                if len(child_path - parent_path) == 1:
                    child_node, = child_path - parent_path
                    tree[parent_node].append(child_node)
                    Q.append((child_path, child_node))

        return tree

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
