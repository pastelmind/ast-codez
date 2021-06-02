import networkx as nx
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import pairwise_distances
import numpy as np
import pandas as pd

from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from scipy import stats

import matplotlib.pyplot as plt 
import seaborn as sns
from sklearn.cluster import KMeans


# HYPER-PARAMETERS
seed = 96
n_clusters = 8
THRESHOLD = 0.0069 # of max distance within cluster

def most_neighbours(clusters, indices, key, metric = "cosine"):
  cluster = clusters[key]
  distances = pairwise_distances(cluster, metric = metric)
  G = nx.from_numpy_array(np.multiply(distances, ((distances > THRESHOLD) - np.eye(len(cluster)))))
  i = sorted(G.degree, key=lambda x: x[1], reverse=True)[0][0]
  return i, indices[key][i]


def get_K_embeds(embeds, K=16, seed=92):

  gmm = GaussianMixture(n_components=K, covariance_type='full', random_state=seed)
  # kmeans = KMeans(n_clusters=K, init="k-means++", random_state=seed)

  gmm_labels = gmm.fit_predict(embeds)
  # kmeans_labels = kmeans.fit_transform(embeds)

  clusters = {}
  indices = {}

  for i in range(K):
    clusters[i] = []
    indices[i] = []

  for i in range(len(gmm_labels)):
    clusters[gmm_labels[i]].append(embeds[i])
    indices[gmm_labels[i]].append(i)


  K_embeds = {}
  for i in range(K):
    local_i, global_i = most_neighbours(clusters, indices, i)
    K_embeds[i] = (clusters[i][local_i], global_i)

  return K_embeds





embs = np.load('embedded.npy')

n_clusters = 8


model_name = "kmeans"

kmeans = KMeans(n_clusters=n_clusters,
                    init="k-means++",
                    random_state=seed)
kmeans_data = kmeans.fit_transform(embs)



pca = PCA(n_components=50, random_state=seed)
pca_data = pca.fit_transform(embs)

tsne = TSNE(n_components=2, random_state=seed)
proj_embs = tsne.fit_transform(pca_data)


data = pd.DataFrame()
data["x"] = proj_embs[:,0]
data["y"] = proj_embs[:,1]
data["cluster"] = np.argmin(kmeans_data, 1)

plt.figure(figsize=(12, 12))
sns_plot = sns.scatterplot(
    x="x", y="y",
    hue="cluster",
    palette=sns.color_palette("hls", n_clusters),
    data=data,
    legend=None,
    alpha=0.9
)
sns_plot.get_figure().savefig(model_name + "_tsne+pca.jpeg")

