import bpy
from bpy.types import Panel
from bpy.props import BoolProperty


class MeshRelSettings(bpy.types.PropertyGroup):
    is_nrel: BoolProperty(name="N.REL")
    is_crel: BoolProperty(name="C.REL")
    is_rrel: BoolProperty(name="R.REL")
    receives_shadows: BoolProperty(name="Receives shadows", default=True)
    receives_fog: BoolProperty(name="Affected by fog", default=False)
    is_transparent: BoolProperty(name="Transparent", default=False)
    generate_mipmaps: BoolProperty(name="Generate Mipmaps (slow)", default=False, description="Generate mipmaps for any textures that this mesh uses")
    is_chunk: BoolProperty(name="Chunk marker", description="Object is used as a chunk marker. All meshes are automatically assigned to the nearest chunk marker.", default=False)


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
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        settings = context.object.rel_settings
        self.layout.active = settings.is_nrel
        col = self.layout.column(align=True)
        col.prop(settings, "receives_shadows")
        col.prop(settings, "receives_fog")
        col.prop(settings, "is_transparent")
        col.prop(settings, "generate_mipmaps")


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
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
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
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        settings = context.object.rel_settings
        self.layout.prop(settings, "is_chunk")
