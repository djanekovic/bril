import logging
import json
import sys

# TODO: handle nonlocal elements

class LVN_TableRow:
    def __init__(self, idx, value, variable):
        self.idx = idx
        self.value = value
        self.variable = variable

    def __repr__(self):
        return f"{{idx: {self.idx}, value: {self.value}, variable: {self.variable}}}"

COMMUTATIVE_OPS = "add", "mul", "eq", "and", "or"

compute_value = {
    "add": lambda x, y: x + y,
    "mul": lambda x, y: x * y,
    "and": lambda x, y: x and y,
    "or": lambda x, y: x or y,
    "not": lambda x: not x,
    "div": lambda x, y: x / y,
    "eq": lambda x, y: x == y,
    "le": lambda x, y: x <= y,
    "lt": lambda x, y: x < y,
    "ge": lambda x, y: x >= y,
    "gt": lambda x, y: x > y,
}

class LVN():
    def __init__(self):
        # map from variable name to idx of LVN_TableRow
        self._environment = {}
        # this is just a list of LVN_TableRows
        self._table = []

    def get_row_with_cannonical_value(self, value):
        """
        Return first row that has the same cannonical value or None otherwise
        """
        return next((row for row in self._table if row.value == value), None)

    def cannonicalize_val(self, instr):
        '''Generate cannonical value representation
        '''
        if instr["op"] == "const":
            return ("const", instr["value"])
        args_idx = [self._table[self._environment[arg]].idx for arg in instr["args"]]
        logging.debug(f"Instr['args']: {instr['args']}, args_idx: {args_idx}")

        # check if some args are compile time constants, if yes, do const propagation
        arg_rows = [self._table[arg] for arg in args_idx]
        if all(map(lambda x: x.value[0] == "const", arg_rows)):
            logging.debug("All args are compile time constants -> doing constant propagation")
            # This is a bit complicated... x.value is tuple so here I get [(True,), (False,)]
            # I have to go over each one more to in order to pull first element, after that
            # I have list of values such as True, False or 42
            args = [i[0] for i in map(lambda x: x.value[1:], arg_rows)]
            try:
                val = ("const", compute_value[instr["op"]](*args))
            except ZeroDivisionError:
                val = ("const", 0)
            logging.debug(f"Generated {instr} -> {val}")
            return val

        if instr["op"] in COMMUTATIVE_OPS:
            return (instr["op"], sorted(args_idx))
        return (instr["op"], args_idx)

    def get_cannonical_variable_names(self, variables):
        return [self._table[self._environment[var]].variable for var in variables]

    def reconstruct_instr(self, instr, variable, value):
        new_instr = instr

        # if cannonical variables are the same we can just copy values
        if self._table[self._environment[variable]].variable != variable:
            logging.debug("We have exact match, we can just copy value")
            # TODO: if we are matching compile time constant, it would be better to generate const than id
            new_instr = {"op": "id", "type": "int", "dest": variable, "args": [self._table[self._environment[variable]].variable] }
        elif "args" not in instr:
            new_instr = instr
        else:
            new_instr["args"] = self.get_cannonical_variable_names(instr["args"])
        logging.debug(f"Generated new instr: {new_instr}")
        return new_instr

    def update_table(self, value, variable):
        # find cannonical variable for that value
        new_row_idx = len(self._table)
        new_row = LVN_TableRow(new_row_idx, value, variable)

        logging.debug(f"Adding new row: {new_row}")
        logging.debug(f"Linking {variable} -> {new_row}")
        self._table.append(new_row)
        self._environment[variable] = new_row_idx

    def reconstruct_block(self, block):
        new_block = []
        for instr in block:
            # this is not a value operation
            if "dest" not in instr:
                logging.debug(f"Handling non value instr: {instr}")
                if "args" not in instr:
                    # this is a label
                    new_block.append(instr)
                    continue

                # find cannonical home for args
                instr["args"] = [self._table[self._environment[arg]].variable for arg in instr["args"]]
                new_block.append(instr)
                continue

            logging.debug(f"Table and env before iteration {self._table}, {self._environment}")
            logging.debug(f"We are LVN-ing this instr: {instr}")
            # 1. cannonicalize value
            val = self.cannonicalize_val(instr)
            # 2. query the table, do we have that value already?
            row = self.get_row_with_cannonical_value(val)
            variable = instr["dest"]
            if row is not None:
                # 3. reuse the value since we have it in a table already
                # we will generate a simple copy instruction

                # get idx of a row where val is in the table
                self._environment[variable] = row.idx
                logging.debug(f"Value exists in the table, I am just adding link {variable} -> {row}")
            else:
                logging.debug("Value does not exist in the table, we are adding it")

                # 4. add new row in the table
                self.update_table(val, variable)

            logging.debug(f"Reconstructing instr: {instr} with cannonical_value: {val} and variable name {variable}")
            new_block.append(self.reconstruct_instr(instr, variable, val))
            logging.debug("\n")

        return new_block


def lvn(block):
    lvn = LVN()

    new_block = lvn.reconstruct_block(block)

    return new_block


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


def main():
    prog = json.load(sys.stdin)

    for i, function in enumerate(prog["functions"]):
        new_function = []
        for block in form_blocks(function):
            new_block = lvn(block)
            new_function += new_block
        prog["functions"][i]["instrs"] = new_function

    print (json.dumps(prog, indent=2))

if __name__ == "__main__":
    #logging.basicConfig(level=logging.DEBUG)
    main()
