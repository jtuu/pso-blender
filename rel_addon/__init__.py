from multiprocessing import current_process

# Trying to work around weird issue with multiprocessing on Windows
if current_process().name == "MainProcess":
    from .rel_addon import *

    if __name__ == "__main__":
        register()
