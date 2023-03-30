import bpy
from bpy.props import BoolProperty


class MeshRelSettings(bpy.types.PropertyGroup):
    is_nrel: BoolProperty(name="N.REL")
    is_crel: BoolProperty(name="C.REL")
    is_rrel: BoolProperty(name="R.REL")


class MeshRelSettingsPanel(bpy.types.Panel):
    bl_label = "REL Settings"
    bl_idname = "OBJECT_PT_MeshRelSettingsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(self, context):
        return context.object.type == "MESH"
    
    def draw(self, context):
        settings = context.object.rel_settings
        row = self.layout.row(heading="Export as:")
        row.prop(settings, "is_nrel")
        row.prop(settings, "is_crel")
        row.prop(settings, "is_rrel")
