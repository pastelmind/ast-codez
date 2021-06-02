from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from nltk.tokenize import word_tokenize
from sklearn.metrics.pairwise import cosine_similarity
# Uncomment to install dependencies
# import nltk
# nltk.download('punkt')

import json
import jsonlines
import os
import numpy as np

raw_data_path = "chunks/data6.jsonl"
target_data_path = "embeddings/embedded.npy"
code_model_path = "doc2vec_weights/code.model"
edit_model_path = "doc2vec_weights/edit.model"

exists = os.path.exists(code_model_path) and os.path.exists(edit_model_path)

with jsonlines.open(raw_data_path) as reader:
        data = [line for line in reader]

if(not exists):

    tagged_before = []
    tagged_after = []
    edit_actions = []

    for i, d in enumerate(data):
        before = TaggedDocument(words=word_tokenize(d['before_code']), tags=['b' + str(i)])
        after = TaggedDocument(words=word_tokenize(d['after_code']), tags=['a' + str(i)])
        A = TaggedDocument(words = d['edit_actions'], tags=[str(i)])
        
        tagged_before.append(before)
        tagged_after.append(after)
        edit_actions.append(A)


    code_data = tagged_before + tagged_after
    edit_data = edit_actions

    seed = 96

    code_config = {
        "epochs": 40,
        "vec_size": 50,
        "alpha": 0.025
    }
    
    edit_config = {
        "epochs": 20,
        "vec_size": 50,
        "alpha": 0.025
    }


    # model for code before and after
    code_model = Doc2Vec(vector_size=code_config['vec_size'],
                    alpha=code_config['alpha'], 
                    min_alpha=0.00025,
                    min_count=1,
                    dm = 1,
                    seed = seed)

    edit_model = Doc2Vec(vector_size=edit_config['vec_size'],
                    alpha=edit_config['alpha'], 
                    min_alpha=0.00025,
                    min_count=1,
                    dm = 1,
                    seed = seed)
    
    code_model.build_vocab(code_data)
    edit_model.build_vocab(edit_data)

    # code before and after
    for epoch in range(code_config['epochs']):
        print('model 1 iteration {0}'.format(epoch))
        code_model.train(code_data,
                    total_examples=code_model.corpus_count,
                    epochs=code_model.epochs)
        
        code_model.alpha -= 0.0002
        code_model.min_alpha = code_model.alpha
    
    # edit actions
    for epoch in range(edit_config['epochs']):
        print('model 1 iteration {0}'.format(epoch))
        edit_model.train(edit_data,
                    total_examples=edit_model.corpus_count,
                    epochs=edit_model.epochs)
        
        edit_model.alpha -= 0.0002
        edit_model.min_alpha = edit_model.alpha


    code_model.save(code_model_path)
    edit_model.save(edit_model_path)

else:

    code_model = Doc2Vec.load(code_model_path)
    edit_model = Doc2Vec.load(edit_model_path)


embedded = np.empty((len(data), int(edit_model.vector_size)))

for i in range(len(data)):

    A_vector = edit_model[str(i)]

    # v_before = code_model['b' + str(i)].reshape(1, -1)
    # v_after = code_model['a' + str(i)].reshape(1, -1)

    # difference = cosine_similarity(v_before, v_after)

    # print(edit_model[str(i)])
    # print(data[i]['edit_actions'])

    embedded[i] = A_vector

np.save(target_data_path, embedded)

    

