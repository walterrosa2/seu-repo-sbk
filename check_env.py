# check_env.py
from pprint import pprint
import config

print(">>> Config carregado de:", config.__file__)

from config import get_settings

s = get_settings()
print("\n>>> Campos carregados no Settings:\n")
pprint(vars(s))
