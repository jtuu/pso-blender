import bpy
from bpy.props import PointerProperty
from bpy.app.handlers import persistent, load_post
from .export_menu import ExportRel, CUSTOM_PT_export_settings
from .properties_menu import MeshRelSettings, MeshRelSettingsPanel


@persistent
def convert_legacy_properties(arg):
    for obj in bpy.data.objects:
        if "nrel" in obj:
            obj.rel_settings.is_nrel = True
            del obj["nrel"]
        if "crel" in obj:
            obj.rel_settings.is_crel = True
            del obj["crel"]
        if "rrel" in obj:
            obj.rel_settings.is_rrel = True
            del obj["rrel"]
load_post.append(convert_legacy_properties)


def menu_func_export(self, context):
    self.layout.operator(ExportRel.bl_idname, text="Export RELs (PSO)")


# Register and add to the "file selector" menu
def register():
    bpy.utils.register_class(ExportRel)
    bpy.utils.register_class(CUSTOM_PT_export_settings)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.utils.register_class(MeshRelSettings)
    bpy.utils.register_class(MeshRelSettingsPanel)
    bpy.types.Object.rel_settings = PointerProperty(type=MeshRelSettings)


def unregister():
    bpy.utils.unregister_class(ExportRel)
    bpy.utils.unregister_class(CUSTOM_PT_export_settings)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(MeshRelSettings)
    bpy.utils.unregister_class(MeshRelSettingsPanel)
    del bpy.types.Object.rel_settings
