from typing import Any,cast
import numpy as np
import tensorflow as tf
from tensorflow import keras
from srl.base.rl.base import RLTrainer
from srl.rl.models.tf.input_block import InputBlock
from .dqn import CommonInterfaceParameter,Config,RemoteMemory
kl = keras.layers

class _QNetwork(keras.Model):
    def __init__(self,config: Config,**kwargs):
        super().__init__(**kwargs)
        self.__input_shape = config.observation_shape
        self.in_block = InputBlock(config.observation_shape,config.env_observation_type)
        if self.in_block.use_image_layer:
            self.image_block = config.image_block.create_block_tf(enable_time_distributed_layer = False)
            self.image_flatten = kl.Flatten()
        self.hidden_block = config.hidden_block.create_block_tf()
        self.out_layer = kl.Dense(
            config.action_num,
            activation = "linear",
            kernel_initializer = "truncated_normal",
            bias_initializer = "truncated_normal",
        )
        self.build(None,) + config.observation_shape)
      
    @tf.function
    def call(self,x,training = False):
        return self._call(x,training)
      
    def _call(self,x,training = False):
        x = self.in_block(x,training = training)
        if self.in_block.use_image_layer:
            x = self.image_block(x,training = training)
            x = self.image_flatten(x)
        x = self.hidden_block(x,training = training)
        x = self.out_layer(x,training = training)
        return x
      
    def build(self,input_shape):
        self.__input_shape = input_shape
        super().build(self.__input_shape)
      
    def summary(self,name = "",**kwargs):
        if hasattr(self.in_block,"init_model_graph"):
            self.in_block.init_model_graph()
        if self.in_block.use_image_layer and hasattr(self.image_block,"init_model_graph"):
            self.image_block.init_model_graph()
        if hasattr(self.hidden_block,"init_model_graph"):
            self.hidden_block.init_model_graph()
        x = kl.Input(shape = self.__input_shape[1:])
        name = self.__class__.__name__ if name == "" else name
        model = keras.Model(inputs = x,outputs = self._call(x),name = name)
        model.summary(**kwargs)

class Parameter(CommonInterfaceParameter):
    def __init__(self,*args):
        super().__init__(*args)
        self.config: Config = self.config
        self.q_online = _QNetwork(self.config,name = "Q_online")
        self.q_target = _QNetwork(self.config,name = "Q_target")
      
    def call_restore(self,data: Any,**kwargs) -> None:
        self.q_online.set_weights(data)
        self.q_target.set_weights(data)
      
    def call_backup(self,**kwargs) -> Any:
        return self.q_online.summary(**kwargs)
      
    def predict_q(self,state: np.ndarray) -> np.ndarray:
        return self.q_online.call(state).numpy()
      
    def predict_target_q(self,state: np.ndarray) -> np.ndarray:
        return self.q_target(state).numpy()

class Trainer(RLTrainer):
    def __init__(self,*args):
        super().__init__(*args)
        self.config: Config = self.config
        self.parameter: Parameter = self.parameter
        self.remote_memory: RemoteMemory = self.remote_memory
        self.optimizer = keras.optimizers.Adam(learning_rate = self.config.lr)
        self.loss_func = keras.losses.Huber()
        self.train_count = 0
        self.sync_count = 0
      
    def get_train_count(self):
        return self.train_count
      
    def train(self):
        if self.remote_memory.length() < self.config.memory_warmup_size:
            return {}
        indices,batchs,weights=self.remote_memory.sample(self.config.batch_size,self.train_count)
        target_q,states,onehot_actions = self.parameter.calc_target_q(batchs,training = True)
        with tf.GradientTape() as tape:
            q = self.parameter.q_online(states)
            q = tf.reduce_sum(q * onehot_actions,axis = 1)
            loss = self.loss_func(target_q * weights, q * weights)
            loss += tf.reduce_sum(self.parameter.q_online.losses)
        grads = tape.gradient(loss,self.parameter.q_online.trainable_variables)
        self.optimizer.apply_gradients(zip(grads,self.parameter.q_online.trainable_variables))
        td_errors = target_q - cast(Any,q).numpy()
        self.remote_memory.update(indices,batchs,td_errors)
        if self.train_count % self.config.target_model_update_interval == 0:
            self.parameter.q_target.set_weights(self.parameter.q_online.get_weights())
            self.sync_count += 1
        self.train_count += 1
        return {"loss": loss.numpy(),"sync": self.sync_count}
