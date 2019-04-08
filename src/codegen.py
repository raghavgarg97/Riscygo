import pickle
import argparse
import random
import re

set_of_activations = []
struct_length = {}
code = []
current_activation = "global"
reg_map = [[None] * 10, [None] * 8]
asm = None
cur_reg = []


class activation_record:
    def __init__(self, previous=None):
        self.previous = previous
        self.label = "global"
        self.data = {}
        self.total = 0
        self.ret_value_addr = None


def get_name(ind1, ind2):
    if ind1 == 0:
        return "$t" + str(ind2)
    else:
        return "$s" + str(ind2)


def get_empty_register(set_name=None):
    global asm
    global set_of_activations
    global current_activation
    global cur_reg
    # Pick from temporary
    for x in range(0, 10):
        if reg_map[0][x] == None and (0, x) not in cur_reg:
            reg_map[0][x] = set_name
            cur_reg.append((0, x))
            return (0, x)
    # Pick from saved
    for x in range(0, 8):
        if reg_map[1][x] == None and (1, x) not in cur_reg:
            reg_map[1][x] = set_name
            cur_reg.append((1, x))
            return (1, x)

    ind1 = random.randint(0, 1)
    if ind1 == 0:
        ind2 = random.randint(0, 9)
    else:
        ind2 = random.randint(0, 7)

    while (ind1, ind2) in cur_reg:
        ind1 = random.randint(0, 1)
        if ind1 == 0:
            ind2 = random.randint(0, 9)
        else:
            ind2 = random.randint(0, 7)

    record = get_rec(reg_map[ind1][ind2])
    record["isreg"] = -1
    if record["label"] == "global":
        asm.write("sw " + get_name(ind1, ind2) + "," +
                  str(-record["func_offset"]) + "($v1)\n")
    else:
        asm.write("sw " + get_name(ind1, ind2) + "," +
                  str(-record["func_offset"]) + "($fp)\n")

    reg_map[ind1][ind2] = set_name
    cur_reg.append((ind1, ind2))
    return (ind1, ind2)


def get_reg(name):
    global set_of_activations
    global current_activation
    global cur_reg

    if type(name) == int or type(name) == float:
        reg = get_empty_register()
        reg_name = get_name(reg[0], reg[1])
        asm.write("li " + reg_name + "," + str(name) + "\n")
        return reg_name

    if name[0] == '*':
        # Deferencing a var
        name = name[1:]
        assert (name[:3] == 'var')
        rec = get_rec(name)
        off = rec['func_offset']
        reg = get_empty_register()
        asm.write('lw ' + get_name(*reg) + ',' + str(-off))
        if rec['label'] == 'global':
            asm.write('($v1)\n')
        else:
            asm.write('($fp)\n')
        asm.write('lw ' + get_name(*reg) + ',0(' + get_name(*reg) + ')\n')
        return get_name(*reg)
    elif name[0] == '&':
        # Getting an address of var
        name = name[1:]
        assert (name[:3] == 'var')
        rec = get_rec(name)
        off = rec['func_offset']
        reg = get_empty_register()
        asm.write('addi ' + get_name(*reg))
        if rec['label'] == 'global':
            asm.write(',($v1),')
        else:
            asm.write(',($fp),')
        asm.write(str(-rec['func_offset']) + '\n')
        return get_name(*reg)
    elif len(name.split('.')) != 1:
        # Getting member of a struct
        member = name.split('.')[1]
        name = name.split('.')[0]
        assert (name[:3] == 'var')
        rec = get_rec(name)
        off = rec['func_offset']
        reg = get_empty_register()
        if rec['width'] == 0:
            asm.write('lw ' + get_name(*reg) + ',' + str(-off + int(member)))
            if rec['label'] == 'global':
                asm.write('($v1)\n')
            else:
                asm.write('($fp)\n')
        else:
            asm.write('lw ' + get_name(*reg) + ',' + str(-off))
            if rec['label'] == 'global':
                asm.write('($v1)\n')
            else:
                asm.write('($fp)\n')
            asm.write('lw ' + get_name(*reg) + ',' + member + '(' +
                      get_name(*reg) + ')\n')
        return get_name(*reg)
    elif len(name.split('[')) != 1:
        # Getting array member
        index = name.split('[')[1].split(']')[0]
        name = name.split('[')[0]
        assert (name[:3] == 'var' and index[:3] == 'var')
        # Load the value of index
        rec = get_rec(index)
        off = rec['func_offset']
        regi = get_empty_register()
        asm.write('lw ' + get_name(*regi) + ',' + str(-off))
        if rec['label'] == 'global':
            asm.write('($v1)\n')
        else:
            asm.write('($fp)\n')
        rec = get_rec(name)
        off = rec['func_offset']
        if rec['width'] == 0:
            asm.write('add ' + get_name(*regi) + ',' + get_name(*regi) + ',')
            if rec['label'] == 'global':
                asm.write('$v1\n')
            else:
                asm.write('$fp\n')
            asm.write('lw ' + get_name(*regi) + ',' + str(-off) + '(' +
                      get_name(*regi) + ')\n')
        else:
            reg = get_empty_register()
            asm.write('lw ' + get_name(*reg) + ',' + str(-off))
            if rec['label'] == 'global':
                asm.write('($v1)\n')
            else:
                asm.write('($fp)\n')
            # load the value at reg + regi
            asm.write('add ' + get_name(*reg) + ',' + get_name(*reg) + ',' +
                      get_name(*regi) + '\n')
            asm.write('lw ' + get_name(*regi) + ',0(' + get_name(*reg) + ')\n')
        return get_name(*regi)
    else:
        # A normal var
        assert (name[:3] == 'var')
        rec = get_rec(name)
        if rec['isreg'] != -1:
            cur_reg.append(rec['isreg'])
            return get_name(*rec['isreg'])
        else:
            reg = get_empty_register(name)
            off = rec['func_offset']
            rec['isreg'] = reg
            asm.write('lw ' + get_name(*reg) + ',' + str(-off))
            if rec['label'] == 'global':
                asm.write('($v1)\n')
            else:
                asm.write('($fp)\n')
            return get_name(*reg)


def get_rec(name):
    global set_of_activations
    global current_activation

    if name in set_of_activations[current_activation].data:
        return set_of_activations[current_activation].data[name]
    else:
        return set_of_activations["global"].data[name]


def off_load():
    for x in range(0, 10):
        if reg_map[0][x] != None:
            record = get_rec(reg_map[0][x])
            record["isreg"] = -1
            if record["label"] == "global":
                asm.write("sw " + get_name(0, x) + "," +
                          str(-record["func_offset"]) + "($v1)\n")
            else:
                asm.write("sw " + get_name(0, x) + "," +
                          str(-record["func_offset"]) + "($fp)\n")
            reg_map[0][x] = None
    for x in range(0, 8):
        if reg_map[1][x] != None:
            record = get_rec(reg_map[1][x])
            record["isreg"] = -1
            if record["label"] == "global":
                asm.write("sw " + get_name(1, x) + "," +
                          str(-record["func_offset"]) + "($v1)\n")
            else:
                asm.write("sw " + get_name(1, x) + "," +
                          str(-record["func_offset"]) + "($fp)\n")
            reg_map[1][x] = None


def handle_assign(dst, src):
    global asm
    # TODO: Handle floating point registers

    if dst[:3] == "var":
        reg = get_reg(src)
        reg2 = get_reg(dst)
        asm.write("move " + reg2 + "," + reg + "\n")

    elif dst[0] == "*":
        reg = get_reg(src)
        reg_emp = get_empty_register()
        reg2 = get_name(reg_emp[0], reg_emp[1])
        rec = get_rec(dst[1:])
        asm.write("lw " + reg2 + "," + str(-rec["func_offset"]))
        if rec["label"] == "global":
            asm.write("($v1)\n")
        else:
            asm.write("($fp)\n")
        asm.write("sw " + reg + ",0(" + reg2 + ")\n")
    elif dst[-1] == "]":
        reg = get_reg(src)
        dst_nam = dst.split("[")[0]
        index = dst.split("[")[1][:-1]
        rec = get_rec(dst_nam)
        if rec["width"] == 0:
            reg_emp = get_empty_register()
            reg2 = get_name(reg_emp[0], reg_emp[1])
            reg_index = get_reg(index)
            #it should be +func_offset
            asm.write("addi " + reg2 + "," + reg_index + "," +
                      str(rec["func_offset"]) + "\n")
            if rec["label"] == "global":
                asm.write("sub " + reg2 + ",$v1," + reg2 + "\n")
            else:
                asm.write("sub " + reg2 + ",$fp," + reg2 + "\n")
            asm.write("sw " + reg + ",0(" + reg2 + ")\n")


def generate_code(ins):
    global first_func
    global set_of_activations
    global current_activation

    if ins[0] == "=":
        assert (len(ins) == 3)
        handle_assign(ins[1], ins[2])
    elif ins[0] == "returnm":
        if len(ins) == 1:
            off_load()
            asm.write("addi $sp,$sp," + str(set_of_activations["main"].total) +
                      "\n")
            asm.write("lw $fp,0($sp)\n")
            asm.write("addi $sp,$sp,4\n")
            asm.write("addi $sp,$sp," +
                      str(set_of_activations["global"].total) + "\n")
            asm.write("jr $ra\n")

        else:
            reg = get_reg(ins[1])
            ret_off = set_of_activations[current_activation].ret_value_addr
            asm.write("sw " + reg + "," + str(-ret_off) + "($fp)\n")
            off_load()
            asm.write("addi $sp,$sp," +
                      str(set_of_activations[current_activation].total) + "\n")
            asm.write("lw $fp,0($sp)\n")
            asm.write("addi $sp,$sp,4\n")
            asm.write("jr $ra\n")

    elif ins[0] == "return":
        if len(ins) == 2:
            reg = get_reg(ins[1])
            ret_off = set_of_activations[current_activation].ret_value_addr
            asm.write("sw " + reg + "," + str(-ret_off) + "($fp)\n")
        off_load()
        asm.write("addi $sp,$sp," +
                  str(set_of_activations[current_activation].total) + "\n")
        asm.write("lw $fp,0($sp)\n")
        asm.write("addi $sp,$sp,4\n")
        asm.write("jr $ra\n")

    elif len(ins) == 1 and ins[0] == "push":
        asm.write("addi $sp,$sp,-4\n")

    elif len(ins) == 2 and ins[0] == "push":
        if ins[1][:3] == "var":
            rec = get_rec(ins[1])
            if rec["width"] == 0:
                reg_emp = get_empty_register()
                reg2 = get_name(reg_emp[0], reg_emp[1])
                asm.write("li " + reg2 + "," + str(rec["func_offset"]) + "\n")
                if rec["label"] == "global":
                    asm.write("sub " + reg2 + ",$v1," + reg2 + "\n")
                else:
                    asm.write("sub " + reg2 + ",$fp," + reg2 + "\n")
                asm.write("addi $sp,$sp,-4\n")
                asm.write("sw " + reg + ",0($sp)\n")

            else:
                reg = get_reg(ins[1])
                asm.write("addi $sp,$sp,-4\n")
                asm.write("sw " + reg + ",0($sp)\n")
        else:
            reg = get_reg(ins[1])
            asm.write("addi $sp,$sp,-4\n")
            asm.write("sw " + reg + ",0($sp)\n")

    elif len(ins) == 3 and ins[0] == "call":
        asm.write("addi $sp,$sp,-4\n")
        asm.write("sw $ra,0($sp)\n")
        off_load()
        asm.write("jal " + ins[1] + "\n")
        asm.write("lw $ra,0($sp)\n")
        asm.write("addi $sp,$sp,4\n")

    elif len(ins) == 1 and ins[0] == "pop":
        asm.write("addi $sp,$sp,4\n")

    elif len(ins) == 2 and ins[0] == "pop":
        rec = get_rec(ins[1])
        reg_emp = get_empty_register(None)
        reg_name = get_name(reg_emp[0], reg_emp[1])
        asm.write("lw " + reg_name + ",0($sp)\n")
        asm.write("sw " + reg_name + "," + str(-rec["func_offset"]))
        if rec["label"] == "global":
            asm.write("($v1)\n")
        else:
            asm.write("($fp)\n")
        asm.write("addi $sp,$sp,4\n")

    elif len(ins) == 2 and ins[0] == "printInt":
        reg = get_reg(ins[1])
        asm.write("move $a0" + "," + reg + "\n")
        asm.write("li $v0,1\n")
        asm.write("syscall\n")

    elif len(ins) == 2 and ins[0] in set_of_activations and ins[0] == "main":
        off_load()
        asm.write("main:")
        asm.write("move $v1,$sp\n")
        asm.write("move $fp,$sp\n")
        current_activation = "global"
        asm.write("addi $sp,$sp," + str(-set_of_activations["global"].total) +
                  "\n")

    elif len(ins) == 2 and ins[0] == "EndOfDecl":
        #do a function call to save current registers
        asm.write("addi $sp,$sp,-4\n")
        asm.write("sw $fp,0($sp)\n")
        asm.write("move $fp,$sp\n")
        current_activation = "main"
        asm.write("addi $sp,$sp," +
                  str(-set_of_activations[current_activation].total) + "\n")

    elif len(ins) == 2 and ins[0] in set_of_activations:
        off_load()
        asm.write(ins[0] + ins[1] + "\n")
        asm.write("addi $sp,$sp,-4\n")
        asm.write("sw $fp,0($sp)\n")
        asm.write("move $fp,$sp\n")
        current_activation = ins[0]
        asm.write("addi $sp,$sp," +
                  str(-set_of_activations[current_activation].total) + "\n")

    elif len(ins) == 2 and ins[1] == ":":
        off_load()
        asm.write(ins[0] + ins[1] + "\n")

    elif len(ins) == 2 and ins[0] == "goto":
        off_load()
        asm.write("j " + ins[1] + "\n")

    elif len(ins) == 4 and (ins[0] == "<" or ins[0] == "<int"):
        reg1 = get_reg(ins[2])
        reg2 = get_reg(ins[3])
        reg3 = get_empty_register(None)
        reg_name = get_name(reg3[0], reg3[1])
        asm.write("slt " + reg_name + "," + reg1 + "," + reg2 + "\n")
        #CALL A GENERIC FUNCTION HERE
        if ins[1][:3] == "var":
            rec = get_rec(ins[1])
            asm.write("sw " + reg_name + "," + str(-rec["func_offset"]))
            if rec["label"] == "global":
                asm.write("($v1)\n")
            else:
                asm.write("($fp)\n")

    elif len(ins) == 4 and (ins[0] == ">" or ins[0] == ">int"):
        reg1 = get_reg(ins[2])
        reg2 = get_reg(ins[3])
        reg3 = get_empty_register(None)
        reg_name = get_name(reg3[0], reg3[1])
        asm.write("slt " + reg_name + "," + reg2 + "," + reg1 + "\n")
        #CALL A GENERIC FUNCTION HERE
        if ins[1][:3] == "var":
            rec = get_rec(ins[1])
            asm.write("sw " + reg_name + "," + str(-rec["func_offset"]))
            if rec["label"] == "global":
                asm.write("($v1)\n")
            else:
                asm.write("($fp)\n")

    elif len(ins) == 4 and (ins[0] == "<=" or ins[0] == "<=int"):
        reg1 = get_reg(ins[2])
        reg2 = get_reg(ins[3])
        reg3 = get_empty_register(None)
        reg_name = get_name(reg3[0], reg3[1])
        asm.write("slt " + reg_name + "," + reg2 + "," + reg1 + "\n")
        asm.write("xor " + reg_name + "," + reg_name + ",1" + "\n")
        #CALL A GENERIC FUNCTION HERE
        if ins[1][:3] == "var":
            rec = get_rec(ins[1])
            asm.write("sw " + reg_name + "," + str(-rec["func_offset"]))
            if rec["label"] == "global":
                asm.write("($v1)\n")
            else:
                asm.write("($fp)\n")

    elif len(ins) == 4 and (ins[0] == ">=" or ins[0] == ">=int"):
        reg1 = get_reg(ins[2])
        reg2 = get_reg(ins[3])
        reg3 = get_empty_register(None)
        reg_name = get_name(reg3[0], reg3[1])
        asm.write("slt " + reg_name + "," + reg1 + "," + reg2 + "\n")
        asm.write("xor " + reg_name + "," + reg_name + ",1" + "\n")
        #CALL A GENERIC FUNCTION HERE
        if ins[1][:3] == "var":
            rec = get_rec(ins[1])
            asm.write("sw " + reg_name + "," + str(-rec["func_offset"]))
            if rec["label"] == "global":
                asm.write("($v1)\n")
            else:
                asm.write("($fp)\n")

    elif len(ins) == 4 and (ins[0] == "==" or ins[0] == "==int"):

        reg1 = get_reg(ins[2])
        reg2 = get_reg(ins[3])
        reg3 = get_empty_register(None)
        reg4 = get_empty_register(None)
        reg_name1 = get_name(reg3[0], reg3[1])
        reg_name2 = get_name(reg4[0], reg4[1])
        asm.write("slt " + reg_name1 + "," + reg1 + "," + reg2 + "\n")
        asm.write("slt " + reg_name2 + "," + reg2 + "," + reg1 + "\n")
        asm.write("or " + reg_name2 + "," + reg_name1 + "," + reg_name2 + "\n")
        asm.write("xor " + reg_name2 + "," + reg_name2 + ",1" + "\n")
        #CALL A GENERIC FUNCTION HERE
        if ins[1][:3] == "var":
            rec = get_rec(ins[1])
            asm.write("sw " + reg_name2 + "," + str(-rec["func_offset"]))
            if rec["label"] == "global":
                asm.write("($v1)\n")
            else:
                asm.write("($fp)\n")

    elif len(ins) == 4 and (ins[0] == "!=" or ins[0] == "!=int"):
        reg1 = get_reg(ins[2])
        reg2 = get_reg(ins[3])
        reg3 = get_empty_register(None)
        reg4 = get_empty_register(None)
        reg_name1 = get_name(reg3[0], reg3[1])
        reg_name2 = get_name(reg4[0], reg4[1])
        asm.write("slt " + reg_name1 + "," + reg1 + "," + reg2 + "\n")
        asm.write("slt " + reg_name2 + "," + reg2 + "," + reg1 + "\n")
        asm.write("or " + reg_name2 + "," + reg_name1 + "," + reg_name2 + "\n")
        #CALL A GENERIC FUNCTION HERE
        if ins[1][:3] == "var":
            rec = get_rec(ins[1])
            asm.write("sw " + reg_name2 + "," + str(-rec["func_offset"]))
            if rec["label"] == "global":
                asm.write("($v1)\n")
            else:
                asm.write("($fp)\n")

    elif len(ins) == 4 and (ins[0] == "+" or ins[0] == "+int"):
        reg1 = get_reg(ins[2])
        reg2 = get_reg(ins[3])
        reg3 = get_reg(ins[1])
        asm.write("add " + reg3 + "," + reg1 + "," + reg2 + "\n")

    elif len(ins) == 4 and (ins[0] == "-" or ins[0] == "-int"):
        reg1 = get_reg(ins[2])
        reg2 = get_reg(ins[3])
        reg3 = get_reg(ins[1])
        asm.write("sub " + reg3 + "," + reg1 + "," + reg2 + "\n")

    elif len(ins) == 4 and (ins[0] == "*" or ins[0] == "*int"):
        reg1 = get_reg(ins[2])
        reg2 = get_reg(ins[3])
        reg3 = get_reg(ins[1])
        asm.write("mul " + reg3 + "," + reg1 + "," + reg2 + "\n")

    elif len(ins) == 4 and ins[0] == "&&":
        reg1 = get_reg(ins[2])
        reg2 = get_reg(ins[3])
        reg3 = get_reg(ins[1])
        asm.write("and " + reg3 + "," + reg1 + "," + reg2 + "\n")

    # elif len(ins)==4 and (ins[0]=="/" or ins[0]=="/int"):
    #     reg1=get_reg(ins[2])
    #     reg2=get_reg(ins[3])
    #     reg3=get_reg(ins[1])
    #     asm.write("sub " + reg3 + "," +reg1+","+reg2+"\n")

    elif len(ins) == 4 and ins[0] == "iffalse":
        reg = get_reg(ins[1])
        off_load()
        asm.write("beq " + reg + ",$0," + ins[3] + "\n")


def main():
    global set_of_activations
    global struct_length
    global code
    global asm
    global cur_reg

    with open('activation.pickle', 'rb') as handle:
        set_of_activations = pickle.load(handle)
    with open('struct.pickle', 'rb') as handle:
        struct_length = pickle.load(handle)
    with open('code.pickle', 'rb') as handle:
        code = pickle.load(handle)
    parser = argparse.ArgumentParser(description='A Parser for Golang')
    parser.add_argument(
        '--output', required=True, help='Output file for 3 Address Code')
    args = parser.parse_args()
    asm = open(args.output, 'w+')

    print "global_struct_length"
    for nam in struct_length:
        print nam, struct_length[nam]
    for nam in set_of_activations:
        print nam
        for item in set_of_activations[nam].data:
            print item, set_of_activations[nam].data[item][
                "func_offset"], set_of_activations[nam].data[item][
                    "label"], set_of_activations[nam].data[item]["width"]
        print set_of_activations[nam].total
        print set_of_activations[nam].ret_value_addr
    print "\n"
    global_decl = []
    leng = 0
    for decl in code:
        if len(decl) == 2 and decl[0] in set_of_activations:
            break
        else:
            global_decl.append(decl)
            leng += 1
    for i in range(leng):
        del code[0]

    for ind in range(len(code)):
        if len(code[ind]) == 2 and code[ind][0] == 'main':
            code = code[:ind + 1] + global_decl + [["EndOfDecl", ":"]
                                                   ] + code[ind + 1:]
            break

    for i in range(len(code)):
        for j in range(len(code[i])):
            if type(code[i][j]) == str:
                code[i][j] = code[i][j].strip()

    asm.write(".text\n")
    asm.write(".globl main\n")
    print code

    for ins in code:
        generate_code(ins)
        cur_reg = []


if __name__ == '__main__':
    main()
