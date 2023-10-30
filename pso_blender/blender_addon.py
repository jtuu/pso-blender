import bpy
from bpy.props import PointerProperty
from bpy.app.handlers import persistent, load_post
from .rel_export_menu import ExportRel, CUSTOM_PT_export_settings
from .rel_import_menu import ImportRel
from .rel_properties_menu import (
    MeshRelSettings,
    MeshRelSettingsPanel,
    MeshNrelSettingsPanel,
    MeshCrelSettingsPanel,
    MeshRrelSettingsPanel)
from .bml_import_menu import ImportBml
from .bml_export_menu import ExportBml
from .xj_import_menu import ImportXj
from .xj_export_menu import ExportXj
from .xj_material_properties_menu import XjMaterialSettings, XjMaterialSettingsPanel


# @persistent causes an error when this file is executed with fake-bpy-module (unit tests)
# We can detect if the code is actually running inside blender by checking if bpy.app.binary_path is set
if bpy.app.binary_path:
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


rel_import_export_description = "Phantasy Star Online map (.rel)"
bml_import_export_description = "BML (PSO)"
xj_import_export_description = "XJ (PSO)"


def menu_func_export(self, context):
    self.layout.operator(ExportRel.bl_idname, text=rel_import_export_description)
    self.layout.operator(ExportBml.bl_idname, text=bml_import_export_description)
    self.layout.operator(ExportXj.bl_idname, text=xj_import_export_description)


def menu_func_import(self, context):
    self.layout.operator(ImportRel.bl_idname, text=rel_import_export_description)
    self.layout.operator(ImportBml.bl_idname, text=bml_import_export_description)
    self.layout.operator(ImportXj.bl_idname, text=xj_import_export_description)


classes = [
    ExportRel,
    CUSTOM_PT_export_settings,
    ImportRel,
    MeshRelSettings,
    MeshRelSettingsPanel,
    MeshNrelSettingsPanel,
    MeshCrelSettingsPanel,
    MeshRrelSettingsPanel,
    ImportBml,
    ExportBml,
    ImportXj,
    ExportXj,
    XjMaterialSettings,
    XjMaterialSettingsPanel
]


# Register and add to the "file selector" menu
def register():
    # Register classes
    for clazz in classes:
        bpy.utils.register_class(clazz)
    # Add buttons to export and import menus
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    # Add settings panel to object menu
    bpy.types.Object.rel_settings = PointerProperty(type=MeshRelSettings)
    # Add settings panel to material menu
    bpy.types.Material.xj_settings = PointerProperty(type=XjMaterialSettings)
    # Add hooks
    load_post.append(convert_legacy_properties)


def unregister():
    for clazz in classes:
        bpy.utils.unregister_class(clazz)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    del bpy.types.Object.rel_settings
    del bpy.types.Material.xj_settings
    load_post.remove(convert_legacy_properties)
