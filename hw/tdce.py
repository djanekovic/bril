import json
import sys


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

def eliminate_dead_code(function):
    used = set()
    for instr in function["instrs"]:
        if "args" in instr:
            [used.add(args) for args in instr["args"]]

    changed = False
    for instr in function["instrs"]:
        if "dest" in instr and instr["dest"] not in used:
            function["instrs"].remove(instr)
            changed = True

    return changed

def eliminate_double_assignment(block):
    defined = {}
    for instr in block:
        # instruction has arguments and we saw the definition before
        if "args" in instr and any(args in defined for args in instr["args"]):
            # erase the variable name from the definition map
            [defined.pop(args) for args in instr["args"]]
        elif "dest" in instr and instr["dest"] in defined:
            # We are assigning the thing we already assigned
            dead_definition_instr = defined[instr["dest"]]
            block.remove(dead_definition_instr)
            changed = True
        elif "dest" in instr:
            # this is definition, add to the defined
            defined[instr["dest"]] = instr

    changed = False
    return changed

def tdce():
    prog  = json.load(sys.stdin)

    for function in prog["functions"]:
        while eliminate_dead_code(function):
            pass

    for i, function in enumerate(prog["functions"]):
        new_function = []
        for block in form_blocks(function):
            while eliminate_double_assignment(block):
                pass
            new_function += block
        prog["functions"][i]["instrs"] = new_function

    print (json.dumps(prog, indent=2))

if __name__ == "__main__":
    tdce()
