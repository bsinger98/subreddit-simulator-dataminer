import tensorflow as tf
from neuralModel import SmallConfig

config = SmallConfig()
config.batch_size = 1
config.num_steps = 1

saver = tf.train.Saver()

with tf.Session() as sess:
    initializer = tf.random_uniform_initializer(-config.init_scale, config.init_scale)
    saver.restore(sess, "model/model.ckpt-0")