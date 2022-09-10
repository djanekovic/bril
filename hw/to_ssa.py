import sys
import json
import dominance_utils

from cfg import CFG

def get_variable_assignment_map(cfg):
    variable_assignment_map = {}
    for block_name, block in cfg.block_map.items():
        for instr in block:
            if "dest" in instr:
                variable_assignment_map.setdefault(instr["dest"], set()).add(block_name)

    return variable_assignment_map


def insert_phi_nodes(cfg, dom, variable_assignment_map):
    has_already = {x: 0 for x in cfg.cfg.keys()}
    work = {x: 0 for x in cfg.cfg.keys()}
    worklist = set()

    for iter_count, v in enumerate(variable_assignment_map.keys(), start=1):
        # add to the worklist all the nodes where assignment happens
        for x in variable_assignment_map[v]:
            work[x] = iter_count
            worklist.add(x)

        while worklist:
            x = worklist.pop()
            for y in dom.df[x]:
                # for each node in DF check did we add phi node, if not add it
                if has_already[y] < iter_count:
                    y_preds = cfg.predecessors[y]
                    # TODO: add type
                    phi_node = {"op": "phi", "type": "int", "dest": v, "args": [v for preds in y_preds], "labels": y_preds}
                    cfg.block_map[y].insert(0, phi_node)
                    has_already[y] = iter_count
                    if work[y] < iter_count:
                        work[y] = iter_count
                        worklist.add(y)

def recursive_rename(x, dom, cfg, C, S):
    old_block = [instr.copy() for instr in cfg.block_map[x]]

    for instr in cfg.block_map[x]:
        if "args" in instr and instr["op"] != "phi":
            # replace use of V by use of V_i where i = Top(S(V))
            instr["args"] = [f"{v}_{S[v][-1]}" for v in instr["args"]]


        if "dest" not in instr:
            continue

        old_v = instr["dest"]
        i = C[old_v]
        instr["dest"] = f"{old_v}_{i}"
        S[old_v].append(i)
        C[old_v] += 1
    # end of first loop

    for y in cfg.cfg[x]:
        j = cfg.predecessors[y].index(x)

        new_instrs = []
        for instr in cfg.block_map[y]:
            if "op" in instr and instr["op"] == "phi":
                v = instr["args"][j]
                if S[v]:
                    i = S[v][-1]
                    instr["args"][j] = f"{v}_{i}"
                    new_instrs.append(instr)
            else:
                new_instrs.append(instr)
        cfg.block_map[y] = new_instrs

    for y in dom.dominance_tree[x]:
        recursive_rename(y, dom, cfg, C, S)

    for instr in old_block:
        if "dest" in instr and "args" in instr:
            S[instr["dest"]].pop()



def rename_phi_nodes(cfg, dom, variable_assignment_map):
    C = {x: 0 for x in variable_assignment_map.keys()}
    S = {x: [] for x in variable_assignment_map.keys()}

    recursive_rename(list(cfg.block_map)[0], dom, cfg, C, S)


if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for function in prog["functions"]:
        cfg = CFG(function)
        variable_assignment_map = get_variable_assignment_map(cfg)
        dom = dominance_utils.Dominators(cfg)

        insert_phi_nodes(cfg, dom, variable_assignment_map)
        rename_phi_nodes(cfg, dom, variable_assignment_map)

        new_function_instrs = []
        for name, block in cfg.block_map.items():
            new_function_instrs.append({"label": name})
            new_function_instrs += block

        function["instrs"] = new_function_instrs

    print (json.dumps(prog, indent=2))
