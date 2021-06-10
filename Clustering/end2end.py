
import json
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import numpy as np

original_file = "dataset_chunk0/data0.jsonl"

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

vector_size_choices = [5, 10, 20, 40, 50]
n_clusters_choices = [2, 3, 4, 5, 6, 7]
all_silhouette_scores = np.zeros(shape = (len(vector_size_choices), len(n_clusters_choices)), dtype=np.float64)

for i in range(len(vector_size_choices)):
    for j in range(len(n_clusters_choices)):
        vector_size_ = vector_size_choices[i]
        n_clusters_ = n_clusters_choices[j]
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

        # Step 5: Sillihoute score
        silhouette_score_ = silhouette_score(collect_vectors, label)
        all_silhouette_scores[i, j] = silhouette_score_
        print("vector_size_= ", vector_size_, ", n_clusters_ = ", n_clusters_, ", silhouette_score = ", silhouette_score_)
print(all_silhouette_scores)





