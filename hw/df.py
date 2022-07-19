import sys
import json

from form_blocks import form_blocks
from cfg import CFG

"""
Instantiate this class when you want to do reachability analysis on a function

We need a class because we need global descriptor of all definitions in a function.
We will keep a tuple (var_name, global_idx) for example,
first definition of a variable 'a' will get global_idx 0, subsequent definitions will
get 1, 2... Function arguments will have (var_name, -1)
"""
class ReachingDefinitions:
    def __init__(self, block_map):
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
        self.global_definition_mapper = dict()

        definition_cntr = {}
        for block_name, block in block_map.items():
            for instr_idx, instr in enumerate(block):
                if "dest" in instr:
                    dest = instr["dest"]
                    if dest not in definition_cntr:
                        definition_cntr[dest] = 0
                    else:
                        definition_cntr[dest] += 1

                    self.global_definition_mapper[(block_name, instr_idx)] = definition_cntr[dest]


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

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    dataflow_rd(prog)
