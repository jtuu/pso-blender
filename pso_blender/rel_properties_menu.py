import bpy
from bpy.types import Panel
from bpy.props import BoolProperty, IntProperty
from . import c_rel


class MeshRelSettings(bpy.types.PropertyGroup):
    is_nrel: BoolProperty(name="N.REL")
    is_crel: BoolProperty(name="C.REL")
    is_rrel: BoolProperty(name="R.REL")
    receives_shadows: BoolProperty(name="Receives shadows", default=True)
    receives_fog: BoolProperty(name="Affected by fog", default=False)
    is_chunk: BoolProperty(name="Chunk marker", description="Object is used as a chunk marker. All meshes are automatically assigned to the nearest chunk marker.", default=False)
    # Can't figure out how to get IntProperty to support a 32bit unsigned value so I'll just split it into two 16bit values
    collision_flags_value1: IntProperty(default=0, subtype="UNSIGNED")
    collision_flags_value2: IntProperty(default=0, subtype="UNSIGNED")


def make_collision_flag_props():
    prop_keys = []

    def make_flag_getter(flag):
        return lambda settings: (settings.collision_flags_value1 & flag) != 0

    def make_flag_setter(flag):
        return lambda settings, value: (
                setattr(settings, "collision_flags_value1", settings.collision_flags_value1 | flag)
                if value else
                setattr(settings, "collision_flags_value1", settings.collision_flags_value1 & ~flag))

    for flag, name in c_rel.COLLISION_FLAG_NAMES.items():
        key = "collision_flag_" + hex(flag)
        label = "{} ({})".format(name, hex(flag))
        prop = BoolProperty(
            name=label,
            default=False,
            get=make_flag_getter(flag),
            set=make_flag_setter(flag))
        MeshRelSettings.__annotations__[key] = prop
        prop_keys.append(key)
    
    return prop_keys


COLLISION_FLAG_PROP_KEYS = make_collision_flag_props()


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
        self.layout.row(align=True).label(text="Collision flags: " + hex(settings.collision_flags_value1 | (settings.collision_flags_value2 << 16)))
        col = self.layout.column(heading="Collision type:", align=True)
        for prop_key in COLLISION_FLAG_PROP_KEYS:
            col.prop(settings, prop_key)


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
