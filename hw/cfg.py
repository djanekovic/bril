import json
import sys
from collections import OrderedDict


TERMINATORS = ("jmp", "br", "ret")

def form_blocks(function):
    """Iterate every instruction in a function and form a block

    Block should end on terminator instruction (jmp, br and ret)
    or if it is last block in a function. We have to be careful
    not to return empty block.
    """
    block = []
    for instr in function["instrs"]:
        if "op" in instr:               # instr is actually an instruction
            block.append(instr)
            if instr["op"] in TERMINATORS:
                yield block
                block = []
        elif "label" in instr:          # instr is label
            if block:
                yield block
            block = [instr]             # new block begins with this label
        else:
            print ("Unhandled instr in form_blocks: ", instr)
    if block:
        yield block


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


if __name__ == "__main__":
    prog  = json.load(sys.stdin)
    for function in prog["functions"]:
        cfg = CFG(function)
        print (cfg.cfg)
