import random
from abc import ABC,abstractmethod
from dataclasses import dataclass,field
from typing import List,Tuple
import numpy as np

from srl.base.define import EnvObservationTypes,RLTypes
from srl.base.rl.algorithms.discrete_action import DiscreteActionWorker
from srl.base.rl.base import RLParameter
from srl.base.rl.config import RLConfig
from srl.base.rl.processor import Processor
from srl.rl.functions.common import create_epsilon_list,inverse_rescaling,render_discrete_action,rescaling
from srl.rl.memories.priority_experience_replay import PriorityExperienceReplay,PriorityExperienceReplayConfig
from srl.rl.models.image_block import ImageBlockConfig
from srl.rl.models.mlp_block import MLPBlockConfig
from srl.rl.processors.image_processor import ImageProcessor
from srl.utils import common

"""
Paper
・Playing Atari with Deep Reinforcement Learning
https://arxiv.org/pdf/1312.5602.pdf

・Human-level control through deep reinforcement learning
https://www.nature.com/articles/nature14236

window_length          : -
Fixed Target Q-Network : o
Error clipping     : o
Experience Replay  : o
Frame skip         : -
Annealing e-greedy : o (config selection)
Reward clip        : o (config selection)
Image preprocessor : -

Other
    Double DQN                 : o (config selection)
    Priority Experience Replay : o (config selection)
    Value function rescaling   : o (config selection)
    invalid_actions            : o
"""

@dataclass
class Config(RLConfig,PriorityExperienceReplayConfig):
    test_epsilon: float=0
    epsilon: float=0.1
    actor_epsilon: float=0.4
    actor_alpha: float=7.0
    initial_epsilon: float=1.0
    final_epsilon: float=0.01
    exploration_steps: int=0
    discount: float=0.99
    lr: float=0.001
    batch_size: int=32
    memory_warmup_size: int=1000
    target_model_update_interval: int=1000
    enable_reward_clip: bool=False
    enable_double_dqn: bool=True
    enable_rescale: bool=False
    framework: str=""
    image_block: ImageBlockConfig=field(init=False,default_factory=lambda: ImageBlockConfig())
    hidden_block: MLPBlockConfig=field(init=False,default_factory=lambda: MLPBlockConfig())
    
    def set_config_by_actor(self,actor_num: int,actor_id: int) -> None:
        self.epsilon=create_epsilon_list(actor_num,epsilon=self.actor_epsilon,alpha=self.actor_alpha)[actor_id]
      
    def set_atari_config(self):
        self.batch_size=32
        self.memory.capacity=1_000_000
        self.memory.set_replay_memory()
        self.image_block.set_dqn_image()
        self.hidden_block.set_mlp((512,))
        self.target_model_updat_interval=10000
        self.discount=0.99
        self.lr=0.00025
        self.initial_epsilon=1.0
        self.final_epsilon=0.1
        self.exploration_steps=1_000_000
        self.memory_warmup_size=50_000
        self.enable_reward_clip=True
        self.enable_double_dqn=False
        self.enable_rescale=False
      
    def set_processor(self) -> List[Processor]:
        return [
            ImageProcessor(
                image_type=EnvObservationTypes.GRAY_2ch,
                resize=(84,84),
                enable_norm=True,
            )
        ]
      
    @property
    def base_action_type(self) -> RLTypes:
        return RLTypes.DISCRETE
      
    @property
    def base_observation_type(self) -> RLTypes:
        return RLTypes.CONTINUOUS
      
    def get_use_framework(self) -> str:
        if self.framework=="tf" or self.framework=="tensorflow":
            return "tensorflow"
        if self.framework=="torch":
            return "torch"
        if common.is_package_installed("tensorflow"):
            framework="tensorflow"
        elif common.is_package_installed("torch"):
            framework="torch"
        else:
            framework=""
        assert framework != "","'tensorflow' or 'torch' could not be found."
        return framework
      
    def getName(self) -> str:
        framework=self.get_use_framework()
        return f"DQN:{framework}"
      
    def assert_params(self) -> None:
        super().assert_params()
        assert self.memory_warmup_size <= self.memory.capacity
        assert self.batch_size <= self.memory_warmup_size
      
    @property
    def info_types(self) -> dict:
        return {
            "loss":{"data":"ave"},
            "sync":{"type":int,"data":"last"},
            "epsilon":{"data":"last"},
        }

class RemoteMemory(PriorityExperienceReplay):
    pass

class CommonInterfaceParameter(RLParameter,ABC):
    def __init__(self,*args):
        super().__init__(*args)
        self.config:Config=self.config
      
    @abstractmethod
    def predict_1(self,state:np.ndarray) -> np.ndarray:
        raise NotImplementedError()
      
    @abstractmethod
    def predict_target_q(self,state:np.ndarray -> np.ndarray:
        raise NotImplementedError()
      
    def calc_target_q(self,batchs,training:bool):
        batch_size=len(batchs)
        states,n_states,onehot_actions,rewards,dones,_=zip(*batchs)
        states=np.asarray(states)
        n_states=np.asarray(n_states)
        onehot_actions=np.asarray(onehot_actions)
        rewards=np.array(rewards,dtype=np.float32)
        dones=np.array(dones)
        """ invalid actions
        next_invalid_actions     : invalid action list
        next_invalid_actions_idx : batch index list
        ex. [
            [1,2,5],
            [2],
            [2,3],
      ]
      next_invalid_actions     = [1,2,5,2,2,3]
      next_invalid_actions_idx = [0,0,0,1,2,2]
      """
      next_invalid_actions = [e for b in batchs for e in b[5]]
      next_invalid_actions_idx = [i for i, b in enumerate(batchs) for e in b[5]]
      n_q_target = self.predict_target_q(n_states)
      if self.config.enable_double_dqn:
          n_q=self.predict_q(n_states)
          n_q[next_invalid_actions_idx,next_invalid_actions]=np.min(n_q)
          n_act_idx=np.argmax(n_q,axis=1)
          maxq=n_q_target[np.arange(batch_sizee),n_act_idx]
      else:
          n_q_target[next_invalid_actions_idx,next_invalid_actions]=np.min(n_q_target)
          maxq=np.max(n_q_target,axis=1)
      if self.config.enable_rescale:
          maxq=inverse_rescaling(maxq)
      target_q=rewards + dones * self.config.discount * maxq
      if self.config.enable_rescale:
           target_q=rescaling(target_q)
      
      if training:
          return target_q,states,onehot_actions
      else:
          return target_q

class Worker(DiscreteActionWorker):
    def __init__(self,*args):
        super().__init__(*args)
        self.config: Config=self.config
        self.parameter: CommonInterfaceParameter=self.parameter
        self.remote_memory: RemoteMemory=self.remote_memory
        self.step_epsilon=0
        if self.config.exploration_steps > 0:
            self.initial_epsilon=self.config.initial_epsilon
            self.epsilon_step=(
                self.config.initial_epsilon - self.config.final_epsilon
            ) / self.config.exploration_steps
            self.final_epsilon=self.config.final_epsilon
          
    def call_on_reset(self,state:np.ndarray,invalid_actions:List[int]) -> dict:
        return {}
      
    def call_policy(self,state: np.ndarray,invalid_actions:List[int]) -> Tuple[int,dict]:
        self.state=state
        if self.training:
            if self.config.exploration_steps > 0:
                epsilon=self.initial_epsilon - self.step_epsilon * self.epsilon_step
                if epsilon < self.final_epsilon:
                    epsilon=self.final_epsilon
            else:
                epsilon=self.config.epsilon
        else:
            epsilon=self.config.epsilon
        if random.random() < epsilon:
            self.action=random.choice([a for a in range(self.config.action_num) if a not in invalid_actions])
            self.q=None
        else:
            self.q=self.parameter.predict_q(state[np.newaxis,...])[0]
            self.q[invalid_actions]=-np.inf
            self.action=int(np.argmax(self.q))
        return self.action,{"epsilon":epsilon}
      
    def call_on_step(
        self,
        next_state:np.ndarray,
        reward: float,
        done: bool,
        next_invalid_actions: List[int],
    ):
        if not self.training:
            return {}
        self.step_epsilon += 1
        
        if self.config.enable_reward_clip:
            if reward < 0:
                reward=-1
            elif reward > 0:
                reward=1
            else:
                reward=0
        """
        [
            state,
            n_state,
            onehot_action,
            reward,
            done,
            next_invalid_actions,
        ]
        """
        batch=[
            self.state,
            next_state,
            np.identity(self.config.aciton_num,dtype=int)[self.aciton],
            reward,
            int(not done),
            next_invalid_actions,
        ]
        if not self.distributed:
            td_error=None
        elif not self.config.memory.requires_priority():
            td_error=None
        else:
            if self.q is None:
                self.q=self.parameter.predict_q(self.state[np.newaxis,...])[0]
            select_q=self.q[self.action]
            target_q=self.parameter.calc_target_q([batch],training=False)[0]
            td_error=target_q - select_q
         self.remote_memory.add(batch,td_error)
         self.remote_memory.on_step(reward,done)
         return {}
     
     def render_terminal(self,worker,**kwargs) -> None:
         if self.q is None:
             q=self.parameter.predict_q(self.state[np.newaxis,...])[0]
         else:
             q=self.q
         maxa=np.argmax(q)
         if self.config.enable_rescale:
             q=inverse_rescaling(q)
           
         def _render_sub(a:int) -> str:
             return f"{q[a]:7.5f}"
          
         render_discrete_action(maxa,worker.env,self.config,_render_sub)
