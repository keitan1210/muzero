import os
import matplotlib.pyplot as plt
import srl
from srl.algorithms import agent57
from srl.utils import common
common.logger_print()

def main():
    env_config=srl.EnvConfig("Pendulum-v1")
    rl_configs=[]
    base_config=agent57.Config(
        lstm_units=128,
        hidden_layer_sizes=(64,64),
        enable_dueling_network=False,
        target_model_update_interval=100,
        enable_rescale=False,
        burnin=5,
        sequence_length=5,
        enable_retrace=False,
        enable_intrinsic_reward=False,
        actor_num=1,
        input_ext_reward=False,
        input_int_reward=False,
        input_action=False,
    )
    base_config.memory.capacity=100_000
    rl_configs.append(("base",base_config.copy()))
    _c=base_config.copy()
    _c.enable_intrinsic_reward=True
    rl_configs.append(("intrinsic_reward",_c))
    _c=base_config.copy()
    _c.enable_retrace=True
    rl_configs.append(("retrace",_c))
    _c=base_config.copy()
    _c.actor_num=16
    rl_configs.append(("actor_16",_c))
    _c=base_config.copy()
    _c.input_ext_reward=True
    _c.input_int_reward=True
    _c.input_action=True
    rl_configs.append(("UVFA",_c))
    results=[]
    for name,rl_config in rl_configs:
        print(name)
        runner=srl.Runner(env_config,rl_config)
        runner.set_history(write_file=True)
        runner.train_mp(max_train_count=200*200)
        df=runner.get_history().get_df()
        results.append((name,df))
    plt.figure(figsize=(12,6))
    plt.xlabel("episode")
    plt.ylabel("reward")
    for name,df in results:
        df=df[df["name"]=="actor0"]
        plt.plot(df["episode"],df["reward0"].rolling(10).mean(),label=name)
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__),"_agent57.png"))
    plt.show()

if __name__=="__main__":
    main()
