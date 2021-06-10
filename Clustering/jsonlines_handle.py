import jsonlines
dict_list = [{"a": 1}, {"a": 2}]

# read the file
data = []
with jsonlines.open("trial.jsonl") as f:
    for line in f.iter():
        data.append(line)

# write to file
with jsonlines.open("trial.jsonl", mode="w") as outfile:
    for dict_ in dict_list:
        outfile.write(dict_)











