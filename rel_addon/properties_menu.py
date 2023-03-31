import bpy
from bpy.types import Panel
from bpy.props import BoolProperty


class MeshRelSettings(bpy.types.PropertyGroup):
    is_nrel: BoolProperty(name="N.REL")
    is_crel: BoolProperty(name="C.REL")
    is_rrel: BoolProperty(name="R.REL")
    receives_shadows: BoolProperty(name="Receives shadows", default=True)


class MeshNrelSettingsPanel(Panel):
    bl_label = "N.REL"
    bl_idname = "OBJECT_PT_MeshNrelSettingsPanel"
    bl_parent_id = "OBJECT_PT_MeshRelSettingsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(self, context):
        return context.object.type == "MESH"

    def draw_header(self, context):
        self.layout.prop(context.object.rel_settings, "is_nrel", text="")
    
    def draw(self, context):
        settings = context.object.rel_settings
        self.layout.active = settings.is_nrel
        row = self.layout.row()
        row.prop(settings, "receives_shadows")


class MeshCrelSettingsPanel(Panel):
    bl_label = "C.REL"
    bl_idname = "OBJECT_PT_MeshCrelSettingsPanel"
    bl_parent_id = "OBJECT_PT_MeshRelSettingsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(self, context):
        return context.object.type == "MESH"

    def draw_header(self, context):
        self.layout.prop(context.object.rel_settings, "is_crel", text="")
    
    def draw(self, context):
        settings = context.object.rel_settings
        self.layout.active = settings.is_crel
        self.layout.label(text="Nothing here yet")


class MeshRrelSettingsPanel(Panel):
    bl_label = "R.REL"
    bl_idname = "OBJECT_PT_MeshRrelSettingsPanel"
    bl_parent_id = "OBJECT_PT_MeshRelSettingsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(self, context):
        return context.object.type == "MESH"

    def draw_header(self, context):
        self.layout.prop(context.object.rel_settings, "is_rrel", text="")
    
    def draw(self, context):
        settings = context.object.rel_settings
        self.layout.active = settings.is_rrel
        self.layout.label(text="Nothing here yet")


class MeshRelSettingsPanel(Panel):
    bl_label = "REL Settings"
    bl_idname = "OBJECT_PT_MeshRelSettingsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(self, context):
        return context.object.type == "MESH"
    
    def draw(self, context):
        pass
