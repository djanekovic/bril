import logging
import json
import sys

class LVN_TableRow:
    def __init__(self, idx, value, variable):
        self.idx = idx
        self.value = value
        self.variable = variable

    def __repr__(self):
        return f"{{idx: {self.idx}, value: {self.value}, variable: {self.variable}}}"

    def is_const(self):
        return self.value is not None and self.value[0] == "const"

    def is_id(self):
        return self.value is not None and self.value[0] == "id"

    def is_copy_foldable(self):
        return self.is_const() or self.is_id()



COMMUTATIVE_OPS = "add", "mul", "eq", "and", "or"
COMPARISON_OPS = "eq", "lt", "gt", "le", "ge"

compute_value = {
    "add": lambda x, y: x + y,
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

def is_variable_overwritten_later(block, variable, i):
    return next((True for instr in block[i+1:] if "dest" in instr and instr["dest"] == variable), False)

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
        return next((row for row in self._table if row.value is not None and row.value == value), None)

    def is_nonlocal(self, arg):
        return arg not in self._environment

    def add_nonlocal_values_to_table(self, instr):
        for arg in instr["args"]:
            if self.is_nonlocal(arg):
                logging.debug(f"Argument {arg} is non-local")
                self.update_table(None, arg)

    def cannonicalize_val(self, instr):
        '''Generate cannonical value representation.

        Instruction semantics and fold support should be handled here. If you
        reach value we don't have in the table add new row in the table + env
        with value = None.

        Everything else should just work!
        '''
        # check if any of arguments in instr is not in table -> nonlocal
        if "args" in instr and any(self.is_nonlocal(arg) for arg in instr["args"]):
            self.add_nonlocal_values_to_table(instr)

        # Cannonicalization pass starts here

        if instr["op"] == "const":
            return ("const", instr["value"])

        # get table row id of each arg
        args_idx = [self._table[self._environment[arg]].idx for arg in instr["args"]]
        logging.debug(f"Instr['args']: {instr['args']}, args_idx: {args_idx}")
        arg_rows = [self._table[arg] for arg in args_idx]

        # if instr is "id" it has just one argument,
        # that's why I can just take first element
        if instr["op"] == "id" and arg_rows[0].is_copy_foldable():
            # fold copy
            val = arg_rows[0].value
            logging.debug(f"Copy instr {instr} is foldable, generating {val}!")
            return val

        if all(row.is_const() for row in arg_rows):
            logging.debug("All args are compile time constants -> doing constant propagation")
            # List of values such as True, False or 42
            args = [i for i in map(lambda x: x.value[1], arg_rows)]
            try:
                val = ("const", compute_value[instr["op"]](*args))
            except ZeroDivisionError:
                val = ("const", 0)
            logging.debug(f"Generated {instr} -> {val}")
            return val
        elif any(row.is_const() for row in arg_rows):
            const_value = next((row.value[1] for row in arg_rows if row.is_const()))
            if const_value == True and instr["op"] == "or" or const_value == False and instr["op"] == "and":
                val = ("const", const_value)
                logging.debug(f"We can fold instr to {val}");
                return val
        elif instr["op"] in COMPARISON_OPS and args_idx[0] == args_idx[1]:
            # args are not compile time constant but they are the same
            val = ("const", compute_value[instr["op"]](False, False))
            logging.debug(f"Args are the same, we can fold {instr} -> {val}")
            return val

        if instr["op"] in COMMUTATIVE_OPS:
            return (instr["op"], sorted(args_idx))
        return (instr["op"], args_idx)

    def get_cannonical_variable_names(self, variables):
        return [self._table[self._environment[var]].variable for var in variables]

    def reconstruct_instr(self, instr, variable, value):
        new_instr = instr

        # if cannonical variables are the same we can just copy values
        if value[0] == "const":
            logging.debug("We have a const value, generate a const instruction")
            new_instr = {
                    "op": value[0],
                    "type": instr["type"],
                    "dest": instr["dest"],
                    "value": value[1]
            }
        elif value[0] == "id":
            logging.debug("We have a copy value, generate a copy instruction")
            new_instr = {
                    "op": value[0],
                    "type": instr["type"],
                    "dest": instr["dest"],
                    "args": [self._table[value[1][0]].variable]
                    }
        elif self._table[self._environment[variable]].variable != variable:
            logging.debug("We have exact match, we can just copy value")
            # TODO: if we are matching compile time constant,
            # it would be better to generate const than id
            new_instr = {
                    "op": "id",
                    "type": instr["type"],
                    "dest": instr["dest"],
                    "args": self.get_cannonical_variable_names([variable]) }
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
        cnt = 0
        for i, instr in enumerate(block):
            # this is not a value operation
            if "dest" not in instr:
                logging.debug(f"Handling non value instr: {instr}")
                if "args" not in instr:
                    # this is a label
                    new_block.append(instr)
                    continue

                # find cannonical home for args
                instr["args"] = self.get_cannonical_variable_names(instr["args"])
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
                if is_variable_overwritten_later(block, variable, i):
                    instr["dest"] = f"lvn.{cnt}"
                    cnt += 1

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
