import sys
import json

from form_blocks import form_blocks
from cfg import CFG

class ConstantPropagation:
    compute_value = {
        "add": lambda x, y: x + y,
        "sub": lambda x, y: x - y,
        "mul": lambda x, y: x * y,
        "and": lambda x, y: x and y,
        "or": lambda x, y: x or y,
        "div": lambda x, y: x / y,
        "eq": lambda x, y: x == y,
        "le": lambda x, y: x <= y,
        "lt": lambda x, y: x < y,
        "ge": lambda x, y: x >= y,
        "gt": lambda x, y: x > y,
        "not": lambda x: not x,
    }

    def __init__(self, worklist=None):
        self.forward_pass = True

    def init(self, worklist, function=None):
        in_ = {block_name: {} for block_name in worklist.keys()}
        out = {block_name: {} for block_name in worklist.keys()}
        return in_, out

    def transfer(self, block, in_, block_name=None):
        out = {}
        for instr in block:
            # if instruction is a value instruction -> check do we know how to compute its value
            if "dest" in instr:
                if instr["op"] == "const":
                    # const is a special case, update entry in the map
                    in_[instr["dest"]] = instr["value"]
                    print (f"Instr is const, inserting {instr['value']}")
                    continue

                # general case: extract arg names
                args = instr.get("args", [])
                if all(arg in in_ and in_[arg] != '?' for arg in args):
                    # args are constants, we can compute destination
                    value = self.compute_value[instr["op"]](*[in_[arg] for arg in args])
                    print (f"Instr is {instr}, inserting {value}")
                    in_[instr["dest"]] = value
                else:
                    in_[instr["dest"]] = '?'

        return in_


    def merge(self, out_maps):
        # propagate unique keys to the block input
        # non-unique keys that have different values are assigned as "don't know"

        in_map = {}
        for out_map in out_maps:
            for name, value in out_map.items():
                if name not in in_map:
                    in_map[name] = value
                elif in_map[name] != value:
                    in_map[name] = '?'

        return in_map


"""
a  b  c
 \ | /
   n
 / | \ 
d  e  f

Variable is live on exit of the block n if it is live in the entry of the
blocks {a, b, c}.

n_out = in_d U in_e U in_f

Variable is live in the block entry if it was live in the block exit and
this block does not redefine the variable or
if the block uses variable x.

n_in = uses(x) - (n_out - defs(x))

"""
class LiveVariables:
    def __init__(self, worklist=None):
        self.forward_pass = False

    def init(self, worklist, function=None):
        in_ = {block_name: set() for block_name in worklist.keys()}
        out = {block_name: set() for block_name in worklist.keys()}

        last_block_name, last_block = worklist.popitem(last=True)
        in_[last_block_name] = self.transfer(last_block, out[last_block_name])

        return in_, out

    def transfer(self, block, out, block_name=None):
        uses = set()
        local_defs = set()
        for instr in block:
            uses.update(arg for arg in instr.get("args", []) if arg not in local_defs)
            if "dest" in instr:
                local_defs.add(instr["dest"])

        result = uses.union(out.difference(local_defs))

        return result

    def merge(self, in_sets):
        res = set().union(*in_sets)
        print (f"Result: {res}")
        return res


def dataflow_lv(prog):
    for function in prog["functions"]:
        cfg  = CFG(function)
        print (cfg.cfg)
        alg = LiveVariables()

        worklist = cfg.block_map.copy()
        # these are mapping from block to the thing we need, here we are mapping from
        # block to the [(var_name, global_idx)]
        in_ = {block_name: set() for block_name in cfg.block_map.keys()}
        # same as in
        out = {block_name: set() for block_name in cfg.block_map.keys()}

        last_block_name, last_block = worklist.popitem(last=True)
        in_[last_block_name] = alg.transfer(last_block, out[last_block_name])

        print (f"Entering worklist loop, we have in: {in_} and out: {out}")
        print (worklist)
        while len(worklist) > 0:
            block_name, block = worklist.popitem(last=True)
            print (f"Popping {block_name}:{block}")
            out[block_name] = alg.merge(in_[succ] for succ in cfg.cfg[block_name])
            tmp_in = alg.transfer(block, out[block_name], block_name)
            if tmp_in != in_[block_name]:
                in_[block_name] = tmp_in
                for preds in cfg.predecessors[block_name]:
                    worklist[preds] = cfg.block_map[preds]


            print ("\nEnd of an iteration!")
            print (f"Worklist: {worklist}")
            print (f"IN: {in_}, OUT: {out}")


def dataflow_rd(prog):
    for function in prog["functions"]:
        cfg  = CFG(function)
        print (cfg.cfg)
        reaching_definitions = ReachingDefinitions(cfg.block_map)

        worklist = cfg.block_map.copy()
        # these are mapping from block to the thing we need, here we are mapping from
        # block to the [(var_name, global_idx)]
        in_ = {block_name: set() for block_name in cfg.block_map.keys()}
        # same as in
        out = {block_name: set() for block_name in cfg.block_map.keys()}

        first_block_name, first_block = worklist.popitem(last=False)
        if "args" in function:
            [in_[first_block_name].add((arg["name"], -1)) for arg in function["args"]]

        out[first_block_name] = reaching_definitions.transfer(first_block, in_[first_block_name], first_block_name)

        print (f"Entering worklist loop, we have in: {in_} and out: {out}")
        print (worklist)
        while len(worklist) > 0:
            block_name, block = worklist.popitem(last=False)
            print (f"Popping {block_name}:{block}")
            in_[block_name] = reaching_definitions.merge(out[pred] for pred in cfg.predecessors[block_name])
            tmp_out = reaching_definitions.transfer(block, in_[block_name], block_name)
            if tmp_out != out[block_name]:
                out[block_name] = tmp_out
                for succ in cfg.cfg[block_name]:
                    print (succ, worklist, cfg.block_map)
                    worklist[succ] = cfg.block_map[succ]


            print ("\nEnd of an iteration!")
            print (f"Worklist: {worklist}")
            print (f"IN: {in_}, OUT: {out}")


def dataflow_cp(prog):
    for function in prog["functions"]:
        cfg  = CFG(function)
        print (cfg.cfg)
        alg = ConstantPropagation()

        worklist = cfg.block_map.copy()
        in_ = {block_name: {} for block_name in cfg.block_map.keys()}
        out = {block_name: {} for block_name in cfg.block_map.keys()}

        print (f"Entering worklist loop, we have in: {in_} and out: {out}")
        print (worklist)
        while len(worklist) > 0:
            block_name, block = worklist.popitem(last=False)
            print (f"Popping {block_name}:{block}")
            in_[block_name] = alg.merge(out[pred] for pred in cfg.predecessors[block_name])
            tmp_out = alg.transfer(block, in_[block_name], block_name)
            if tmp_out != out[block_name]:
                out[block_name] = tmp_out
                for succ in cfg.cfg[block_name]:
                    print (succ, worklist, cfg.block_map)
                    worklist[succ] = cfg.block_map[succ]


            print ("\nEnd of an iteration!")
            print (f"Worklist: {worklist}")
            print (f"IN: {in_}, OUT: {out}")



"""
Instantiate this class when you want to do reachability analysis on a function

We need a class because we need global descriptor of all definitions in a function.
We will keep a tuple (var_name, global_idx) for example,
first definition of a variable 'a' will get global_idx 0, subsequent definitions will
get 1, 2... Function arguments will have (var_name, -1)
"""
class ReachingDefinitions:
    def __init__(self, worklist):
        """
        Construct ReachingDefinitions pass

        Generate a mapping (block, instr_idx_in_block) -> definition_idx
        For example, if block 1 has:
        a <- 1
        a <- a + 2

        and block 2 has:
        b <- a
        a <- a - 1

        our global_definition_mapper will look like:
        { (1, 0): 0, (1, 1): 1, (2, 1): 2 }
        """
        self.forward_pass = True
        self.global_definition_mapper = dict()

        definition_cntr = {}
        for block_name, block in worklist.items():
            for instr_idx, instr in enumerate(block):
                if "dest" in instr:
                    dest = instr["dest"]
                    if dest not in definition_cntr:
                        definition_cntr[dest] = 0
                    else:
                        definition_cntr[dest] += 1

                    self.global_definition_mapper[(block_name, instr_idx)] = definition_cntr[dest]

    def init(self, worklist, function):
        in_ = {block_name: set() for block_name in worklist.keys()}
        out = {block_name: set() for block_name in worklist.keys()}

        first_block_name, first_block = worklist.popitem(last=False)
        if "args" in function:
            [in_[first_block_name].add((arg["name"], -1)) for arg in function["args"]]
        out[first_block_name] = self.transfer(first_block, in_[first_block_name], first_block_name)

        return in_, out


    def transfer(self, block, in_, block_name):
        """ Compute transfer function
        For reachability analysis transfer function is pretty easy

        out = def U (in - kill)
        """

        print (f"Executing transfer function for block {block_name} and input set: {in_}")
        local_reachable_definitions = {}

        # 1. Local analysis: find the definitions that reach
        # the end of the basic block.
        for i, instr in enumerate(block):
            if "dest" in instr:
                dest = instr["dest"]
                local_reachable_definitions[dest] = self.global_definition_mapper[(block_name, i)]

        print (f"Locally reachable definitions: {local_reachable_definitions}")

        # 2. resolve differences between local and global(in)
        # if same variable is defined in local and global scope, kill it in result
        # Everything in the local scope is surely in the output, we won't insert from in to out
        # if we already have it inside

        res = {(var, idx) for var, idx in local_reachable_definitions.items()}
        for var, idx in in_:
            if var not in local_reachable_definitions:
                res.add((var, idx))

        print (f"Result: {res}")

        return res

    def merge(self, out_sets):
        """ Merge operation of output sets

        For ReachingDefinitions it is pretty simple, just merge all the sets
        """
        print (f"Merging sets: {out_sets}")
        res = set().union(*out_sets)
        print (f"Result: {res}")
        return res


def dataflow(Algorithm):
    for function in prog["functions"]:
        cfg  = CFG(function)
        print (cfg.cfg)
        worklist = cfg.block_map.copy()

        alg = Algorithm(worklist)
        in_, out = alg.init(worklist, function)

        print (f"Entering worklist loop, we have in: {in_} and out: {out}")
        print (worklist)
        while len(worklist) > 0:
            block_name, block = worklist.popitem(last=not alg.forward_pass)
            print (f"Popping {block_name}:{block}")
            if alg.forward_pass:
                in_[block_name] = alg.merge(out[pred] for pred in cfg.predecessors[block_name])
                tmp = alg.transfer(block, in_[block_name], block_name)
                if tmp != out[block_name]:
                    out[block_name] = tmp
                    for succ in cfg.cfg[block_name]:
                        worklist[succ] = cfg.block_map[succ]
            else:
                out[block_name] = alg.merge(in_[succ] for succ in cfg.cfg[block_name])
                tmp = alg.transfer(block, out[block_name], block_name)
                if tmp != in_[block_name]:
                    in_[block_name] = tmp
                    for preds in cfg.predecessors[block_name]:
                        worklist[preds] = cfg.block_map[preds]

            print ("\nEnd of an iteration!")
            print (f"Worklist: {worklist}")
            print (f"IN: {in_}")
            print (f"OUT: {out}")


if __name__ == "__main__":
    prog = json.load(sys.stdin)

    dataflow(ConstantPropagation)
