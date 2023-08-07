import numpy as np
import srl
from srl.algorithms import ql
from srl.envs import sample_env
runner=srl.Runner(srl.EnvConfig("SampleEnv"),rl_config=ql.Config())
runner.train(timeout=10)
rewards=runner.evaluate(max_episodes=100)
print("100エピソードの平均結果",np.mean(rewards))
runner.render_terminal()
render=runner.animation_save_gif("_SampleEnv.gif",render_scale=3)
