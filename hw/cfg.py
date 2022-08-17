import json
import sys
from collections import OrderedDict
from form_blocks import form_blocks

class CFG:
    """
    Control flow graph

    Object represents control flow graph of one function. Graph
    is computed upon construction.
    """
    def __init__(self, function):
        self.function_name = function["name"]
        # mapping from label name to block: {label: block/[instr]}
        self.block_map = self.get_block_map(function)
        # mapping from block_name to all successors of block_name: {label: [label]}
        self.cfg = self.generate_cfg()
        self.vertices = {vertex for vertex in self.cfg.keys()}

        self.predecessors = self.generate_predecessors()

    def get_block_map(self, function):
        block_map = OrderedDict()
        for block in form_blocks(function):
            first_instr = block[0]
            if "label" in first_instr:
                label = first_instr["label"]
                block = block[1:]
            else:
                label = f"label_{len(block_map)}"
            block_map[label] = block
        return block_map

    def generate_cfg(self):
        cfg = {}
        for i, (label, block) in enumerate(self.block_map.items()):
            last_instr = block[-1]

            if last_instr["op"] in ("jmp", "br"):
                cfg[label] = last_instr["labels"]
            elif last_instr["op"] == "ret":
                cfg[label] = []
            else:
                # regular instruction, check if this is the last block -> do nothing
                if i == len(self.block_map) - 1:
                    cfg[label] = []
                else:
                    cfg[label] = [list(self.block_map.keys())[i+1]]
        return cfg

    def generate_predecessors(self):
        predecessors = {label: [] for label in self.cfg.keys()}
        for label, block in self.cfg.items():
            for succs in self.cfg[label]:
                predecessors[succs].append(label)

        return predecessors


if __name__ == "__main__":
    prog  = json.load(sys.stdin)
    for function in prog["functions"]:
        cfg = CFG(function)
        print (cfg.cfg)
