import srl
from srl.algorithms import ql

def main():
    runner=srl.Runner("Grid",ql.Config())
    runner.train(timeout=10)
    rewards=runner.evaluate()
    print(f"evaluate episodes:{rewards}")

if __name__=="__main__":
    main()
