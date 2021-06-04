
import json
import jsonlines
from sklearn.cluster import KMeans
import numpy as np
import os

original_file = "dataset_chunk00/data0.jsonl"

with open(original_file) as json_file:
    data = [json.loads(line) for line in json_file]

# data = [{"name":..., "before_code": ..., "after_code":..., "edit_actions": ["delete-node", "delete-node", "delete-node", "delete-node", "delete-node", "delete-node", "delete-node"]},...]
collect_tokens_edit_actions = [obj_dict["edit_actions"] for obj_dict in data]
# collect_tokens_edit_actions =  [['delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node'], ['delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node'], ['delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node', 'delete-node'], ['update-node', 'move-tree', 'delete-node', 'delete-node'], ['update-node']]

# start gensim
import gensim
train_corpus = []
for i in range(len(collect_tokens_edit_actions)):
    train_corpus.append(gensim.models.doc2vec.TaggedDocument( collect_tokens_edit_actions[i], [i]))

vector_size_ = 5
n_clusters_ = 3
model = gensim.models.doc2vec.Doc2Vec(vector_size=vector_size_, min_count=2, epochs=40)
model.build_vocab(train_corpus)
model.train(train_corpus, total_examples=model.corpus_count, epochs=model.epochs)

# Step 3: collect all the vectors
collect_vectors = []
for h in range(len(data)):
    dict_obj = data[h]
    edit_tokens = dict_obj["edit_actions"]
    pred_vector = model.infer_vector(edit_tokens).tolist()  # a list
    collect_vectors.append(pred_vector)
collect_vectors = np.array(collect_vectors)

# Step 4: K-means clustering
KMean_ = KMeans(n_clusters= n_clusters_)
KMean_.fit(collect_vectors)
label = KMean_.predict(collect_vectors)
# label:  [2 2 2 1... 2]

complete_dict_data = {}
for i in range(n_clusters_):
    complete_dict_data[i] = []

for i in range(len(data)):
    original_obj_dict = data[i]
    cluster_index_ = label[i]
    added_dict = {}
    added_dict["fixed_source_code"] = original_obj_dict["before_code"]
    added_dict["buggy_source_code"] = original_obj_dict["after_code"]
    added_dict["fixed_abstract_code"] = original_obj_dict["before_code_normalized"]
    added_dict["buggy_abstract_code"] = original_obj_dict["after_code_normalized"]
    added_dict["edit_actions"] = original_obj_dict["edit_actions"]
    complete_dict_data[cluster_index_].append(added_dict)
save_dir = "clusters_save"
os.makedirs(save_dir, exist_ok=True)

for i in range(n_clusters_):
    os.makedirs(os.path.join(save_dir, str(i)), exist_ok=False)

for i in range(n_clusters_):
    list_fixed_abstract_code = []
    list_buggy_abstract_code = []
    list_data_dict = []

    for j in range(len(complete_dict_data[i])):
        obj_dict_ = complete_dict_data[i][j]
        list_fixed_abstract_code.append(obj_dict_["fixed_abstract_code"]) #string
        list_buggy_abstract_code.append(obj_dict_["buggy_abstract_code"]) #string
        data_dict = {}
        data_dict["fixed_source_code"] = obj_dict_["fixed_source_code"]
        data_dict["buggy_source_code"] = obj_dict_["buggy_source_code"]
        data_dict["edit_actions"] = obj_dict_["edit_actions"]
        list_data_dict.append(data_dict)

    list_fixed_abstract_code = [ele+"\n" for ele in list_fixed_abstract_code]
    list_buggy_abstract_code = [ele+"\n" for ele in list_buggy_abstract_code]

    cluster_dir = os.path.join(save_dir, str(i))
    data_filepath = os.path.join(cluster_dir, "data.jsonl")
    fixed_abstract_code_filepath = os.path.join(cluster_dir, "fixed_abstract_code.txt")
    buggy_abstract_code_filepath = os.path.join(cluster_dir, "buggy_abstract_code.txt")

    with open(fixed_abstract_code_filepath, "w") as file:
        file.writelines(list_fixed_abstract_code)
    with open(buggy_abstract_code_filepath, "w") as file:
        file.writelines(list_buggy_abstract_code)

    # write to file
    with jsonlines.open(data_filepath, mode="w") as outfile:
        for dict_ in list_data_dict:
            outfile.write(dict_)








































