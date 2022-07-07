import json
import sys

class LVN_TableRow:
    def __init__(self, idx, value, variable):
        self.idx = idx
        self.value = value
        self.variable = variable

    def __repr__(self):
        return f"{{idx: {self.idx}, value: {self.value}, variable: {self.variable}}}"

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
        return (instr["op"], *[self._table[self._environment[arg]].idx for arg in instr["args"]])

    def get_cannonical_variable_names(self, variables):
        return [self._table[self._environment[var]].variable for var in variables]

    def reconstruct_instr(self, instr, variable, value):
        #print (self._table[self._environment[variable]], value)
        new_instr = instr
        if self._table[self._environment[variable]].variable != variable:
            #print ("We have exact match, we can just copy value")
            new_instr = {"op": "id", "type": "int", "dest": variable, "args": [self._table[self._environment[variable]].variable] }
        elif "args" not in instr:
            new_instr = instr
        else:
            new_instr["args"] = self.get_cannonical_variable_names(instr["args"])
        #print ("Generated new instr: ", new_instr)
        return new_instr

    def update_table(self, value, variable):
        # find cannonical variable for that value
        new_row_idx = len(self._table)
        new_row = LVN_TableRow(new_row_idx, value, variable)

        #print ("Adding new row ", new_row)
        #print (f"Linking {variable} -> {new_row}")
        self._table.append(new_row)
        self._environment[variable] = new_row_idx

    def reconstruct_block(self, block):
        new_block = []
        for instr in block:
            # this is not a value operation
            if "dest" not in instr:
                # find cannonical home for args
                instr["args"] = [self._table[self._environment[arg]].variable for arg in instr["args"]]
                new_block.append(instr)
                continue

            #print("Table and env before iteration", self._table, self._environment)
            #print("We are LVN-ing this instr: ", instr)
            # 1. cannonicalize value
            val = self.cannonicalize_val(instr)
            # 2. query the table, do we have that value already?
            row = self.get_row_with_cannonical_value(val)
            variable = instr["dest"]
            if row is not None:
                # 3. reuse the value since we have it in a table already
                # we will generate a simple copy instruction
                # new_block.append({"op": "id", "args": [row.variable]})

                # get idx of a row where val is in the table
                self._environment[variable] = row.idx
                #print (f"Value exists in the table, I am just adding link {variable} -> {row}")
            else:
                #print("Value does not exist in the table, we are adding it")

                # 4. add new row in the table
                self.update_table(val, variable)

            #print (f"Reconstructing instr: {instr} with cannonical_value: {val} and variable name {variable}")
            new_block.append(self.reconstruct_instr(instr, variable, val))
            #print("\n")

        #print ("new block: ", new_block)
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
    main()
