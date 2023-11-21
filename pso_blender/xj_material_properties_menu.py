import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty
from . import xj


def make_enum_prop_items(the_enum):
    return [(str(the_enum.__dict__[name]), name, "", i)
        for (i, name) in enumerate(the_enum.__dict__) if not name.startswith("_")]


class XjMaterialSettings(bpy.types.PropertyGroup):
    generate_mipmaps: BoolProperty(
        name="Generate Mipmaps",
        default=False,
        description="Generate mipmaps for this texture. Can make exporting very slow.")
    src_blend: EnumProperty(
        name="Source",
        default=str(xj.BlendMode.D3DBLEND_SRCALPHA),
        items=make_enum_prop_items(xj.BlendMode))
    dst_blend: EnumProperty(
        name="Destination",
        default=str(xj.BlendMode.D3DBLEND_INVSRCALPHA),
        items=make_enum_prop_items(xj.BlendMode))
    tex_addr_u: EnumProperty(
        name="U",
        default=str(xj.TextureAddressingMode.D3DTADDRESS_MIRROR),
        items=make_enum_prop_items(xj.TextureAddressingMode))
    tex_addr_v: EnumProperty(
        name="V",
        default=str(xj.TextureAddressingMode.D3DTADDRESS_MIRROR),
        items=make_enum_prop_items(xj.TextureAddressingMode))
    material1: IntProperty(name="Unknown 1", default=0)
    material2: IntProperty(name="Unknown 2", default=0)
    lighting: BoolProperty(name="Affected by lighting", default=False)
    camera_space_normals: BoolProperty(name="Camera space normals", default=False)
    normal_type: EnumProperty(
        name="Normal type",
        default={str(xj.NormalType.Vertex)},
        items=make_enum_prop_items(xj.NormalType),
        options={"ENUM_FLAG"})
    diffuse_color_source: EnumProperty(
        name="Diffuse color source",
        default=str(xj.MaterialColorSource.D3DMCS_COLOR1),
        items=make_enum_prop_items(xj.MaterialColorSource))


class XjMaterialSettingsPanel(bpy.types.Panel):
    bl_label = "XJ Settings"
    bl_idname = "MATERIAL_PT_XjMaterialSettingsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    @classmethod
    def poll(self, context):
        return True
    
    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        settings = context.material.xj_settings
        self.layout.prop(settings, "generate_mipmaps")
        self.layout.prop(settings, "lighting")
        # Alpha blending
        blend_box = self.layout.box()
        blend_box.label(text="Alpha blending mode")
        blend_input_col = blend_box.column(align=True)
        blend_input_col.prop(settings, "src_blend")
        blend_input_col.prop(settings, "dst_blend")
        # Texture addressing
        tex_addr_box = self.layout.box()
        tex_addr_box.label(text="Texture addressing mode")
        tex_addr_input_col = tex_addr_box.column(align=True)
        tex_addr_input_col.prop(settings, "tex_addr_u")
        tex_addr_input_col.prop(settings, "tex_addr_v")
        # Other
        self.layout.prop(settings, "camera_space_normals")
        self.layout.prop(settings, "normal_type")
        self.layout.prop(settings, "diffuse_color_source")
        self.layout.prop(settings, "material1")
        self.layout.prop(settings, "material2")
