ex_input = """def IDENTIFIER_0(IDENTIFIER_1=True):
    IDENTIFIER_2 = IDENTIFIER_5.IDENTIFIER_4.IDENTIFIER_3(STR_0)
    if not IDENTIFIER_2:
        return IDENTIFIER_1
    return IDENTIFIER_2.IDENTIFIER_6() in (STR_1, STR_2, STR_3)"""

import tokenize
import io
import re

# put into one line
def python_code_oneline(code):
    # print("helllo world")
    # line = " ".join(code.split("\n"))
    line = ""
    new_tokens = []
    cur_pos = 0
    prev_pos = (0, 0)
    for tok in tokenize.tokenize(io.BytesIO(code.encode('utf-8')).readline):
        # print(tok)
        if tok.type == tokenize.NEWLINE:
            strLen = len(" $NEWLINE ")
            newToken = (tok.type, " $NEWLINE ", (1, cur_pos), (1, cur_pos + strLen), line)
            cur_pos = cur_pos + strLen # update cur_pos
            new_tokens.append(newToken)
            prev_pos = tok.end 
        elif tok.type == tokenize.INDENT:
            strLen = len(" $INDENT ")
            newToken = (tok.type, " $INDENT ", (1, cur_pos), (1, cur_pos + strLen), line)
            cur_pos = cur_pos + strLen # update cur_pos
            new_tokens.append(newToken)
            prev_pos = tok.end 
        elif tok.type == tokenize.DEDENT:
            strLen = len(" $DEDENT ")
            newToken = (tok.type, " $DEDENT ", (1, cur_pos), (1, cur_pos + strLen), line)
            cur_pos = cur_pos + strLen # update cur_pos
            new_tokens.append(newToken)
            prev_pos = tok.end 
        elif tok.type == tokenize.NL:
            strLen = len(" $NEWLINE ")
            newToken = (tok.type, " $NEWLINE ", (1, cur_pos), (1, cur_pos + strLen), line)
            cur_pos = cur_pos + strLen # update cur_pos
            new_tokens.append(newToken)
            prev_pos = tok.end 
        elif tok.type == None:
            break
        else:
            # compare the prev positing
            start = tok.start[1] - prev_pos[1]
            if tok.start[0] > prev_pos[0]:
                start = 1 # just make it into a space
            # start = tok.start[1] - prev_pos[1]
            newToken = (tok.type, tok.string, (1, start + cur_pos), (1, start + cur_pos + len(tok.string)), line)
            cur_pos = start + cur_pos + len(tok.string) # update cur_pos
            new_tokens.append(newToken)
            prev_pos = tok.end 
    # return new_tokens
    # print(new_tokens)
    res = " " * (new_tokens[len(new_tokens) - 1][3][1] - new_tokens[0][3][1])
    # prev_pos = new_tokens[0][3]
    for tok in new_tokens:
        if tok[0] != 62: # skip encoding
            # res += tok[1] + " "* (tok[2][1] - prev_pos[1])
            res = res[:tok[2][1]] + tok[1] + res[tok[2][1]:]
            # print("str: ", len(tok[1]))
            # print("prev, cur, res: ", prev_pos, tok[3], res)
            prev_pos = tok[3]
    return res
    # return tokenize.untokenize(new_tokens).decode('utf-8')

print(python_code_oneline(ex_input))
