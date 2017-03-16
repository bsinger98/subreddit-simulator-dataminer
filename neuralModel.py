from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from DBMetaData import engine, subreddits, posts, comments
from sqlalchemy import select

from random import shuffle
import math
import time

import numpy as np
import tensorflow as tf

import reader

flags = tf.flags
logging = tf.logging

flags.DEFINE_string("model", "small", "A type of model. Possible options are: small, medium, large.")
flags.DEFINE_string("data_path", None, "Where the training/test data is stored.")
flags.DEFINE_string("save_path", None, "Model output directory.")
flags.DEFINE_bool("use_fp16", False, "Train using 16-bit floats instead of 32bit floats")
flags.DEFINE_bool("test", False, "Have network generate sentences")

FLAGS = flags.FLAGS


def data_type():
    return tf.float16 if FLAGS.use_fp16 else tf.float32


class PTBInput(object):
    """The input data."""

    def __init__(self, config, data, name=None):
        self.batch_size = batch_size = config.batch_size
        self.num_steps = num_steps = config.num_steps
        self.epoch_size = ((len(data) // batch_size) - 1) // num_steps
        self.input_data, self.targets = reader.ptb_producer(data, batch_size, num_steps, name=name)


class PTBModel(object):
    """The PTB model."""

    def __init__(self, is_training, config, input_):
        self._input = input_

        batch_size = input_.batch_size
        num_steps = input_.num_steps
        size = config.hidden_size
        vocab_size = config.vocab_size

        # Slightly better results can be obtained with forget gate biases
        # initialized to 1 but the hyperparameters of the model would need to be
        # different than reported in the paper.
        lstm_cell = tf.nn.rnn_cell.BasicLSTMCell(size, forget_bias=0.0, state_is_tuple=True)
        if is_training and config.keep_prob < 1:
            lstm_cell = tf.nn.rnn_cell.DropoutWrapper(lstm_cell, output_keep_prob=config.keep_prob)
        cell = tf.nn.rnn_cell.MultiRNNCell([lstm_cell] * config.num_layers, state_is_tuple=True)

        self._initial_state = cell.zero_state(batch_size, data_type())

        with tf.device("/cpu:0"):
            embedding = tf.get_variable("embedding", [vocab_size, size], dtype=data_type())
            inputs = tf.nn.embedding_lookup(embedding, input_.input_data)

        if is_training and config.keep_prob < 1:
            inputs = tf.nn.dropout(inputs, config.keep_prob)

        # Simplified version of tensorflow.models.rnn.rnn.py's rnn().
        # This builds an unrolled LSTM for tutorial purposes only.
        # In general, use the rnn() or state_saving_rnn() from rnn.py.
        #
        # The alternative version of the code below is:
        #
        # inputs = [tf.squeeze(input_step, [1])
        #           for input_step in tf.split(1, num_steps, inputs)]
        # outputs, state = tf.nn.rnn(cell, inputs,
        # initial_state=self._initial_state)
        outputs = []
        state = self._initial_state
        with tf.variable_scope("RNN"):
            for time_step in range(num_steps):
                if time_step > 0:
                    tf.get_variable_scope().reuse_variables()
                (cell_output, state) = cell(inputs[:, time_step, :], state)
                outputs.append(cell_output)

        output = tf.reshape(tf.concat(1, outputs), [-1, size])
        softmax_w = tf.get_variable("softmax_w", [size, vocab_size], dtype=data_type())
        softmax_b = tf.get_variable("softmax_b", [vocab_size], dtype=data_type())
        logits = tf.matmul(output, softmax_w) + softmax_b
        loss = tf.nn.seq2seq.sequence_loss_by_example([logits],[tf.reshape(input_.targets, [-1])],[tf.ones([batch_size * num_steps], dtype=data_type())])
        self._cost = cost = tf.reduce_sum(loss) / batch_size
        self._final_state = state
        self._output_probs = tf.nn.softmax(logits)

        if not is_training:
            return

        self._lr = tf.Variable(0.0, trainable=False)
        tvars = tf.trainable_variables()
        grads, _ = tf.clip_by_global_norm(tf.gradients(cost, tvars), config.max_grad_norm)
        optimizer = tf.train.GradientDescentOptimizer(self._lr)
        self._train_op = optimizer.apply_gradients(zip(grads, tvars), global_step=tf.contrib.framework.get_or_create_global_step())

        self._new_lr = tf.placeholder(tf.float32, shape=[], name="new_learning_rate")
        self._lr_update = tf.assign(self._lr, self._new_lr)

    def assign_lr(self, session, lr_value):
        session.run(self._lr_update, feed_dict={self._new_lr: lr_value})

    @property
    def input(self):
        return self._input

    @property
    def initial_state(self):
        return self._initial_state

    @property
    def cost(self):
        return self._cost

    @property
    def final_state(self):
        return self._final_state

    @property
    def lr(self):
        return self._lr

    @property
    def train_op(self):
        return self._train_op

    @property
    def output_probs(self):
        return self._output_probs


class SmallConfig(object):
    """Small config."""
    init_scale = 0.1
    learning_rate = 1.0
    max_grad_norm = 5
    num_layers = 2
    num_steps = 20
    hidden_size = 200
    max_epoch = 1
    max_max_epoch = 1
    keep_prob = 1.0
    lr_decay = 0.5
    batch_size = 20
    vocab_size = 17000


class MediumConfig(object):
    """Medium config."""
    init_scale = 0.05
    learning_rate = 1.0
    max_grad_norm = 5
    num_layers = 2
    num_steps = 35
    hidden_size = 650
    max_epoch = 6
    max_max_epoch = 39
    keep_prob = 0.5
    lr_decay = 0.8
    batch_size = 20
    vocab_size = 10000


class LargeConfig(object):
    """Large config."""
    init_scale = 0.04
    learning_rate = 1.0
    max_grad_norm = 10
    num_layers = 2
    num_steps = 35
    hidden_size = 1500
    max_epoch = 14
    max_max_epoch = 55
    keep_prob = 0.35
    lr_decay = 1 / 1.15
    batch_size = 20
    vocab_size = 10000


class TestConfig(object):
    """Tiny config, for testing."""
    init_scale = 0.1
    learning_rate = 1.0
    max_grad_norm = 1
    num_layers = 1
    num_steps = 2
    hidden_size = 2
    max_epoch = 1
    max_max_epoch = 1
    keep_prob = 1.0
    lr_decay = 0.5
    batch_size = 20
    vocab_size = 10000


def run_epoch(session, model, eval_op=None, verbose=False):
    """Runs the model on the given data."""
    start_time = time.time()
    costs = 0.0
    iters = 0
    state = session.run(model.initial_state)

    fetches = {
        "cost": model.cost,
        "final_state": model.final_state,
        "output_probs": model.output_probs
    }
    if eval_op is not None:
        fetches["eval_op"] = eval_op

    for step in range(model.input.epoch_size):
        feed_dict = {}
        for i, (c, h) in enumerate(model.initial_state):
            feed_dict[c] = state[i].c
            feed_dict[h] = state[i].h

        print(fetches)
        print(feed_dict)
        vals = session.run(fetches, feed_dict)
        cost = vals["cost"]
        state = vals["final_state"]
        probs = vals["output_probs"]

        chosen_word = np.argmax(probs, 1)

        costs += cost
        iters += model.input.num_steps

        if verbose and step % (model.input.epoch_size // 10) == 10:
            print("%.3f perplexity: %.3f speed: %.0f wps" %
                  (step * 1.0 / model.input.epoch_size, np.exp(costs / iters),
                   iters * model.input.batch_size / (time.time() - start_time)))

    return np.exp(costs / iters)

def predict_batch_with_model(session, model):
    """Predicts Word with the model"""
    start_time = time.time()
    costs = 0.0
    iters = 0
    state = session.run(model.initial_state)

    fetches = {
        "output_probs": model.output_probs
    }
    batch = []
    for step in range(model.input.epoch_size):
        feed_dict = {}
        for i, (c, h) in enumerate(model.initial_state):
            feed_dict[c] = state[i].c
            feed_dict[h] = state[i].h

        vals = session.run(fetches, feed_dict)
        probs = vals["output_probs"]

        prediction = np.argmax(probs, 1)
        word = prediction[-1]
        batch.append(word)

    return batch


def get_config():
    if FLAGS.model == "small":
        return SmallConfig()
    elif FLAGS.model == "medium":
        return MediumConfig()
    elif FLAGS.model == "large":
        return LargeConfig()
    elif FLAGS.model == "test":
        return TestConfig()
    else:
        raise ValueError("Invalid model: %s", FLAGS.model)


def main(_):

    config = get_config()
    eval_config = get_config()
    eval_config.batch_size = 1
    eval_config.num_steps = 1
    if(not FLAGS.test):
        conn = engine.connect()

        data = []

        commentSelect = select([comments.c.body]).limit(1000)
        rows = conn.execute(commentSelect)
        for row in rows:
            data.append(row)
        # Randomize data for 3 training groups
        shuffle(data)
        dataLen = math.floor(len(data) / 3)
        trainData = data[0:dataLen]
        validData = data[dataLen:dataLen * 2]
        testData = data[dataLen * 2:dataLen * 3]

        raw_data = reader.ptb_raw_data(trainData, validData, testData, FLAGS.data_path)
        train_data, valid_data, test_data, vocabulary = raw_data

        with tf.Graph().as_default():
            initializer = tf.random_uniform_initializer(-config.init_scale, config.init_scale)

            with tf.name_scope("Train"):
                train_input = PTBInput(config=config, data=train_data, name="TrainInput")
                with tf.variable_scope("Model", reuse=None, initializer=initializer):
                    m = PTBModel(is_training=True, config=config, input_=train_input)
                tf.scalar_summary("Training Loss", m.cost)
                tf.scalar_summary("Learning Rate", m.lr)
                tf.scalar_summary("Logits", m.output_probs)

            with tf.name_scope("Valid"):
                valid_input = PTBInput(config=config, data=valid_data, name="ValidInput")
                with tf.variable_scope("Model", reuse=True, initializer=initializer):
                    mvalid = PTBModel(is_training=False, config=config, input_=valid_input)
                tf.scalar_summary("Validation Loss", mvalid.cost)

            with tf.name_scope("Test"):
                test_input = PTBInput(config=config, data=test_data, name="TestInput")
                with tf.variable_scope("Model", reuse=True, initializer=initializer):
                    mtest = PTBModel(is_training=False, config=eval_config, input_=test_input)

            sv = tf.train.Supervisor(logdir=FLAGS.save_path)
            with sv.managed_session() as session:
                for i in range(config.max_max_epoch):
                    lr_decay = config.lr_decay ** max(i - config.max_epoch, 0.0)
                    m.assign_lr(session, config.learning_rate * lr_decay)

                    print("Epoch: %d Learning rate: %.3f" % (i + 1, session.run(m.lr)))
                    train_perplexity = run_epoch(session, m, eval_op=m.train_op, verbose=True)
                    print("Epoch: %d Train Perplexity: %.3f" % (i + 1, train_perplexity))
                    valid_perplexity = run_epoch(session, mvalid)
                    print("Epoch: %d Valid Perplexity: %.3f" % (i + 1, valid_perplexity))

                test_perplexity = run_epoch(session, mtest)
                print("Test Perplexity: %.3f" % test_perplexity)


                # Generate Sentences
                number_of_sentences = 10  # generate 10 sentences one time
                sentence_cnt = 0
                text = '\n'
                end_of_sentence_char = vocabulary['<eos>']
                id_to_word = {y:x for x,y in vocabulary.items()}

                print('hello')
                wordIds = predict_batch_with_model(session, mtest)
                words = []
                for wordId in range(len(wordIds)):
                    word = id_to_word[wordIds[wordId]]
                    words.append(word)

                print(words)

                '''input_char = np.array([[end_of_sentence_char]])
                run_input = PTBInput(config=config, data=input_char, name="RunInput")
                state = session.run(mtest.initial_state)

                while sentence_cnt < number_of_sentences:
                    feed_dict = {mtest.input: run_input, mtest.initial_state: state}
                    probs, state = session.run([mtest.output_probs, mtest.final_state],feed_dict=feed_dict)
                    sampled_char = pick_from_weight(probs[0])
                    if sampled_char == end_of_sentence_char:
                        text += '.\n'
                        sentence_cnt += 1
                    else:
                        text += ' ' + id_to_word[sampled_char]
                    input_char = np.array([[sampled_char]])
                print(text)
                '''
                if FLAGS.save_path:
                    print("Saving model to %s." % FLAGS.save_path)
                    sv.saver.save(session, FLAGS.save_path, global_step=sv.global_step)
    else:
        with tf.Graph().as_default():
            initializer = tf.random_uniform_initializer(-config.init_scale, config.init_scale)
            data = [1];
            test_input = PTBInput(config=config, data=data, name="TestInput")
            with tf.variable_scope("Model", reuse=False, initializer=initializer):
                mtest = PTBModel(is_training=False, config=config, input_=test_input)

            sv = tf.train.Supervisor(logdir=FLAGS.save_path)
            with sv.managed_session() as session:
                sv.saver.restore(session, 'model/model.ckpt-0');

if __name__ == "__main__":
    tf.app.run()
