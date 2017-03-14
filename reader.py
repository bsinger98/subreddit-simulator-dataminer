"""Utilities for parsing PTB text files."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import os

import tensorflow as tf

def convert_tupleList(data):
  singleList = []
  for comment in data:
    words = comment[0].split();
    words.append("<eos>");
    singleList = singleList + words;

  return singleList;
  
def _build_vocab(data):
  data = convert_tupleList(data);
  
  counter = collections.Counter(data)
  count_pairs = sorted(counter.items(), key=lambda x: (-x[1], x[0]))

  words, _ = list(zip(*count_pairs))
  word_to_id = dict(zip(words, range(len(words))))

  return word_to_id


def _file_to_word_ids(data, word_to_id):
  data = convert_tupleList(data)
  return [word_to_id[word] for word in data if word in word_to_id]


def ptb_raw_data(train_data, valid_data, test_data, data_path):
  """Load PTB raw data from data directory "data_path".
  Reads PTB text files, converts strings to integer ids,
  and performs mini-batching of the inputs.
  The PTB dataset comes from Tomas Mikolov's webpage:
  http://www.fit.vutbr.cz/~imikolov/rnnlm/simple-examples.tgz
  Args:
    data_path: string path to the directory where simple-examples.tgz has
      been extracted.
  Returns:
    tuple (train_data, valid_data, test_data, vocabulary)
    where each of the data objects can be passed to PTBIterator.
  """
  
  #print(data_path);
  # train_path = os.path.join(data_path, "ptb.train.txt")
  # valid_path = os.path.join(data_path, "ptb.valid.txt")
  # test_path = os.path.join(data_path, "ptb.test.txt")

  word_to_id = _build_vocab(train_data)
  #word_to_id = _build_vocab(train_path)
  
  train_data = _file_to_word_ids(train_data, word_to_id)
  valid_data = _file_to_word_ids(valid_data, word_to_id)
  test_data = _file_to_word_ids(test_data, word_to_id)
  
  return train_data, valid_data, test_data, word_to_id


def ptb_producer(raw_data, batch_size, num_steps, name=None):
  """Iterate on the raw PTB data.
  This chunks up raw_data into batches of examples and returns Tensors that
  are drawn from these batches.
  Args:
    raw_data: one of the raw data outputs from ptb_raw_data.
    batch_size: int, the batch size.
    num_steps: int, the number of unrolls.
    name: the name of this operation (optional).
  Returns:
    A pair of Tensors, each shaped [batch_size, num_steps]. The second element
    of the tuple is the same data time-shifted to the right by one.
  Raises:
    tf.errors.InvalidArgumentError: if batch_size or num_steps are too high.
  """
  with tf.name_scope(name, "PTBProducer", [raw_data, batch_size, num_steps]):
    raw_data = tf.convert_to_tensor(raw_data, name="raw_data", dtype=tf.int32)

    data_len = tf.size(raw_data)
    batch_len = data_len // batch_size
    data = tf.reshape(raw_data[0 : batch_size * batch_len],
                      [batch_size, batch_len])

    epoch_size = (batch_len - 1) // num_steps
    assertion = tf.assert_positive(
        epoch_size,
        message="epoch_size == 0, decrease batch_size or num_steps")
    with tf.control_dependencies([assertion]):
      epoch_size = tf.identity(epoch_size, name="epoch_size")

    i = tf.train.range_input_producer(epoch_size, shuffle=False).dequeue()
    x = tf.slice(data, [0, i * num_steps], [batch_size, num_steps])
    y = tf.slice(data, [0, i * num_steps + 1], [batch_size, num_steps])
    return x, y