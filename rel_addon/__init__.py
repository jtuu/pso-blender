from multiprocessing import current_process


bl_info = {
    "name": "Export RELs (PSO)",
    "blender": (3, 4, 0),
    "category": "Export",
}


# Trying to work around weird issue with multiprocessing on Windows
if current_process().name == "MainProcess":
    from .rel_addon import *

    if __name__ == "__main__":
        register()
