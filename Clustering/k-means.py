import jsonlines
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import numpy as np
original_file = "dataset_chunk0/new_data0.jsonl"

# read the file
data = []
with jsonlines.open(original_file) as f:
    for line in f.iter():
        data.append(line)

collect_vectors = [dict_["edit_vector"] for dict_ in data]
# collect_vectors is a list of vector represented by list
collect_vectors = np.array(collect_vectors)

KMean_ = KMeans(n_clusters=3)
KMean_.fit(collect_vectors)
label = KMean_.predict(collect_vectors)
print(label[:20])
print("silhouette_score = ", silhouette_score(collect_vectors, label))





























