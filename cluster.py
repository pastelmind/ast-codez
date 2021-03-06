import networkx as nx
# from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import pairwise_distances
import numpy as np
import pandas as pd

from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

import matplotlib.pyplot as plt 
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
import jsonlines

# HYPER-PARAMETERS
seed = 96
n_clusters = 5
THRESHOLD = 0.4 # of max distance within cluster

def choose_node(cluster, indices, key):
  distances = pairwise_distances(cluster, metric = "cosine")
  G = nx.from_numpy_array(np.multiply(distances, ((distances > THRESHOLD) - np.eye(len(cluster)))))
  i = nx.pagerank(G)
  i = max(i, key=i.get)
  return indices[key][i]


def get_K_samples(embeds, labels, K):

  indices = {}
  for i in range(K):
    indices[i] = []

  for i in range(len(labels)):
    indices[labels[i]].append(i)

  K_embeds = {}
  for i in range(K):
    cluster = [embeds[ind] for ind, cl in enumerate(labels) if cl == i] 
    K_embeds[i] = choose_node(cluster, indices, i)

  return K_embeds

print('Loading embeddings...')
embs = np.load('embeddings/embedded6.npy')

kmeans = KMeans(n_clusters=n_clusters, init="k-means++", random_state=seed)
gmm = GaussianMixture(n_components=n_clusters, covariance_type='full', random_state=seed)

print('Clustering...')
# gmm_labels = gmm.fit_predict(embs)
kmeans_labels = kmeans.fit_predict(embs)


print('Sampling...')
# Sampling
K_examples = get_K_samples(embs, kmeans_labels, n_clusters)


raw_data_path = "chunks/data6.jsonl"

with jsonlines.open(raw_data_path) as reader:
  data = [line for line in reader]

representative = []
for i in K_examples.keys():
  index = K_examples[i]
  representative.append( data[index] )


with jsonlines.open('samples/samples.jsonl', mode='w') as writer:
  for repr in representative:
    writer.write(repr)



pca = PCA(random_state=seed)
pca_data = pca.fit_transform(embs)

tsne = TSNE(n_components=2, random_state=seed)
proj_embs = tsne.fit_transform(pca_data)


data = pd.DataFrame()
data["x"] = proj_embs[:,0]
data["y"] = proj_embs[:,1]

data["cluster"] = kmeans_labels
model_name = "kmeans"
# model_name = "gmm"
# data["cluster"] = gmm_labels


plt.figure(figsize=(12, 12))
sns_plot = sns.scatterplot(
    x="x", y="y",
    hue="cluster",
    palette=sns.color_palette("hls", n_clusters),
    data=data,
    legend=None,
    alpha=0.9
)
sns_plot.get_figure().savefig("visuals/" + model_name + "_" + str(n_clusters) + "_tsne+pca.jpeg")

