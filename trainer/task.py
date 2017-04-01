# Load LSTM network and generate text
import sys
import numpy
import math
from keras.models import Sequential
from keras.layers import Dense
from keras.layers import Dropout
from keras.layers import LSTM
from keras.callbacks import ModelCheckpoint
from keras.utils import np_utils

# Use for getting data from cloud
#from google.cloud import storage
#storage_client = storage.Client()
#bucket = storage_client.get_bucket('subredditsimulator')
#blob = bucket.blob('data/data.txt')
# raw_text = blob.download_as_string().decode('UTF-8').split()

# Use for getting data from local
raw_text = open('data/data.txt').read()
raw_text = raw_text[:100000]

# create mapping of unique words to integers
words = sorted(list(set(raw_text)))
word_to_int = dict((c, i) for i, c in enumerate(words))

# summarize the loaded data
n_words = len(raw_text)
n_vocab = len(words)
print("Total Words: ", n_words)
print("Total Vocab: ", n_vocab)
# prepare the dataset of input to output pairs encoded as integers
seq_length = 500
dataX = []
dataY = []
for i in range(0, n_words - seq_length, 1):
	seq_in = raw_text[i:i + seq_length]
	seq_out = raw_text[i + seq_length]
	dataX.append([word_to_int[word] for word in seq_in])
	dataY.append(word_to_int[seq_out])
n_patterns = len(dataX)
print("Total Patterns: ", n_patterns)
# reshape X to be [samples, time steps, features ]
X = numpy.reshape(dataX, (n_patterns, seq_length, 1))
# normalize
X = X / float(n_vocab)
# one hot encode the output variable
y = np_utils.to_categorical(dataY)

# define the LSTM model
model = Sequential()
model.add(LSTM(256, input_shape=(X.shape[1], X.shape[2]), return_sequences=True))
model.add(Dropout(0.2))
model.add(LSTM(256))
model.add(Dropout(0.2))
model.add(Dense(y.shape[1], activation='softmax'))
model.compile(loss='categorical_crossentropy', optimizer='adam')

# define the checkpoint
filepath="models/weights-improvement-bigger-{epoch:02d}-{loss:.4f}.hdf5"
checkpoint = ModelCheckpoint(filepath, monitor='loss', verbose=1, save_best_only=True, mode='min')
callbacks_list = [checkpoint]
# fit the model
model.fit(X, y, epochs=20, batch_size=128, callbacks=callbacks_list)
