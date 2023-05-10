from multiprocessing import current_process


bl_info = {
    "name": "Phantasy Star Online (PSO) file formats",
    "blender": (3, 4, 0),
    "category": "Import-Export",
}


# Trying to work around weird issue with multiprocessing on Windows
if current_process().name == "MainProcess":
    from .blender_addon import register, unregister

    if __name__ == "__main__":
        register()
