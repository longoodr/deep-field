from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
from scipy.special import softmax
from tensorflow.keras.layers import Activation, Dense, Flatten, InputLayer
from tensorflow.keras.losses import kullback_leibler_divergence as kl_div
from tensorflow.keras.models import Sequential
from tensorflow.keras.utils import to_categorical

from deepfield.dbmodels import init_db
from deepfield.enums import Outcome
from deepfield.model.models import Batcher, PlayerRatings, PredictionModel
from deepfield.playgraph.graph import LevelTraversal

NUM_STATS = len(Outcome)
LAYER_LENGTHS = [32, 16]

init_db()
m = Sequential()
m.add(InputLayer((NUM_STATS, NUM_STATS,)))
m.add(Flatten())
for num_units in LAYER_LENGTHS:
    m.add(Dense(num_units, activation="relu"))
m.add(Dense(len(Outcome)))
m.add(Activation("softmax"))
m.compile("adam", kl_div)
model = PredictionModel(m)
ratings = PlayerRatings(NUM_STATS)

num_seen = 0
reset_after = 32
tot_kl_div = 0
while True:
    ratings.reset()
    for level in LevelTraversal():
        level = list(level)
        outcomes = np.asarray([n["outcome"] for n in level])
        one_hots = to_categorical(outcomes, num_classes=len(Outcome))
        y = Batcher.pad_batch(one_hots)
        diffs = ratings.get_node_pairwise_diffs(level)
        x = Batcher.pad_batch(diffs)
        weights = Batcher.get_padded_weights(diffs.shape[0])
        kl_divs = model.backprop(x, y, weights)
        tot_kl_div += np.sum(kl_divs)
        for i, node in enumerate(level):
            delta = to_categorical(node["outcome"], NUM_STATS) * kl_divs[i]
            ratings.update(delta, node["batter_id"], node["pitcher_id"])
        num_seen += len(level)
        if num_seen >= reset_after:
            reset_after = int(reset_after * 1.1)
            print(f"{tot_kl_div / num_seen:.3f}")
            num_seen = 0
            tot_kl_div = 0
