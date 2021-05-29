
# we need to create a new data0.jsonl file
import json
import jsonlines
original_file = "dataset_chunk0/data0.jsonl"
target_file = "dataset_chunk0/new_data0.jsonl"

with open(original_file) as json_file:
    data = [json.loads(line) for line in json_file]

# data = [{"name":..., "before_code": ..., "after_code":..., "edit_actions": ["delete-node", "delete-node", "delete-node", "delete-node", "delete-node", "delete-node", "delete-node"]},...]
collect_tokens_edit_actions = [obj_dict["edit_actions"] for obj_dict in data]
# collect_tokens_edit_actions =  [['delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node'], ['delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node'], ['delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node'], ['update-node', 'move-tree', 'delete-node', 'delete-node'], ['update-node']]

# start gensim
import os
import gensim
train_corpus = []
for i in range(len(collect_tokens_edit_actions)):
    train_corpus.append(gensim.models.doc2vec.TaggedDocument( collect_tokens_edit_actions[i], [i]))
# collect_tagged =  [TaggedDocument(words=['delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node'], tags=[0]), TaggedDocument(words=['delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node'], tags=[1]), TaggedDocument(words=['delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node'], tags=[2]), TaggedDocument(words=['update-node', 'move-tree', 'delete-node', 'delete-node'], tags=[3]), TaggedDocument(words=['update-node'], tags=[4])]

model = gensim.models.doc2vec.Doc2Vec(vector_size=50, min_count=2, epochs=40)
model.build_vocab(train_corpus)
model.train(train_corpus, total_examples=model.corpus_count, epochs=model.epochs)

vector = model.infer_vector(["delete-node", "delete-node", "delete-node", "delete-node", "delete-node", "delete-node", "delete-node"])
print(vector)

complete_data = []
for i in range(len(data)):
    dict_obj = data[i]
    edit_tokens = dict_obj["edit_actions"]
    pred_vector = model.infer_vector(edit_tokens).tolist() # a list
    dict_obj["edit_vector"] = pred_vector
    complete_data.append(dict_obj)
# complete_data =  [{'name': '', 'before_code': "", 'after_code': "", 'edit_actions': ['delete-node', 'delete-node', ... 'delete-node', 'delete-node'], 'edit_vector': [-0.08472482115030289, 0.012375250458717346,... 0.01512592937797308, 0.029376231133937836]}, ...]

# write result to a file
with jsonlines.open(target_file, mode="w") as outfile:
    for dict_obj in complete_data:
        outfile.write(dict_obj)

