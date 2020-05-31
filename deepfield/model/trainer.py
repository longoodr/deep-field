from abc import ABC, abstractmethod
from math import sqrt
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
from scipy.special import softmax
from tensorflow.keras.layers import (Activation, Dense, Dropout, Flatten,
                                     GaussianNoise, InputLayer,
                                     LayerNormalization, PReLU)
from tensorflow.keras.losses import kullback_leibler_divergence as kl_div
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.optimizers import Nadam
from tensorflow.keras.utils import to_categorical

from deepfield.dbmodels import init_db
from deepfield.enums import Outcome
from deepfield.model.models import (Batcher, PlayerRating, PlayerRatings,
                                    PredictionModel)
from deepfield.playgraph.graph import LevelTraversal

NUM_NEURONS = 1024*20

init_db()
ratings = PlayerRatings()
m = Sequential()
m.add(InputLayer(ratings.get_matchup_rating(0, 0).size))
m.add(Dense(len(Outcome), activation="softmax"))
m.compile("nadam", kl_div)
model = PredictionModel(m)
m.summary()

tot_seen = 0
num_seen = 0
reset_after = 1024
tot_kl_div = 0
passes = 0
while True:
    ratings.reset()
    for level in LevelTraversal():
        level = list(level)
        outcomes = np.asarray([n["outcome"] for n in level])
        one_hots = to_categorical(outcomes, num_classes=len(Outcome))
        x = Batcher.pad_batch(ratings.get_matchup_ratings(level))
        y = Batcher.pad_batch(one_hots)
        weights = Batcher.get_padded_weights(len(level))
        kl_divs = model.backprop(x, y, weights)
        tot_kl_div += np.sum(kl_divs)
        predictions = model.predict(x)[:len(level)]
        for i, (node, one_hot) in enumerate(zip(level, one_hots)):
            outcome = node["outcome"]
            ratings.update(one_hot, node["batter_id"], node["pitcher_id"])
        num_seen += len(level)
        tot_seen += len(level)
        if num_seen >= reset_after:
            print(f"{tot_kl_div / num_seen:1.3f}, {num_seen:7d}, {passes:3d}, {tot_seen}")
            num_seen = 0
            tot_kl_div = 0
    passes += 1
