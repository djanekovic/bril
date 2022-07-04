import json
import sys
from collections import OrderedDict

def generate_graphviz_code(cfg, function_name):
    def generate_graphviz_vertices():
        return "\n".join([f"  {key};" for key in cfg.keys()])

    def generate_graphviz_edges():
        return "\n".join([f"  {key} -> {value};" for key, values in cfg.items() for value in values])

    return f"""
digraph {function_name} {{
{generate_graphviz_vertices()}
{generate_graphviz_edges()}
}}
    """

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


def get_label_block_map(function):
    label2block = OrderedDict()
    for block in form_blocks(function):
        first_instr = block[0]
        if "label" in first_instr:
            label = first_instr["label"]
            block = block[1:]
        else:
            label = f"label_{len(label2block)}"
        label2block[label] = block
    return label2block

class CFG:
    def __init__(self, function):
        self.function_name = function["name"]
        self.cfg = self.generate_cfg(function)


    def generate_cfg(self, function):
        label2block = get_label_block_map(function)

        # key in label2block is cfg vertex
        # we need to add edges and we are done

        cfg = {}
        for i, (label, block) in enumerate(label2block.items()):
            last_instr = block[-1]

            if last_instr["op"] in ("jmp", "br"):
                cfg[label] = last_instr["labels"]
            elif last_instr["op"] == "ret":
                cfg[label] = []
            else:
                # regular instruction, check if this is the last block -> do nothing
                if i == len(label2block) - 1:
                    cfg[label] = []
                else:
                    cfg[label] = [list(label2block.keys())[i+1]]
        return cfg



def get_graphviz_cfg():
    prog = json.load(sys.stdin)

    for function in prog["functions"]:
        cfg = CFG(function)
        graphviz_code = generate_graphviz_code(cfg.cfg, cfg.function_name)
        print (graphviz_code)


if __name__ == "__main__":
    get_graphviz_cfg()
