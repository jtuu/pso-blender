import os, sys, math
from dataclasses import dataclass, field
from warnings import warn
import bpy.types
from .rel import Rel
from .serialization import Serializable, Numeric
from . import util, xvm


U8 = Numeric.U8
U16 = Numeric.U16
U32 = Numeric.U32
I8 = Numeric.I8
I16 = Numeric.I16
I32 = Numeric.I32
F32 = Numeric.F32
Ptr32 = Numeric.Ptr32
NULLPTR = Numeric.NULLPTR


@dataclass
class Color(Serializable):
    # Purple default
    r: U8 = 0xff
    g: U8 = 0
    b: U8 = 0xff
    a: U8 = 0xff


@dataclass
class VertexFormat1(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    u: F32 = 0.0
    v: F32 = 0.0


@dataclass
class VertexFormat4(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    diffuse: Color = field(default_factory=Color)


@dataclass
class VertexFormat5(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    diffuse: Color = field(default_factory=Color)
    u: F32 = 0.0
    v: F32 = 0.0


@dataclass
class VertexBufferFormat1(Serializable):
    vertices: list[VertexFormat1] = field(default_factory=list)


@dataclass
class VertexBufferFormat4(Serializable):
    vertices: list[VertexFormat4] = field(default_factory=list)


@dataclass
class VertexBufferFormat5(Serializable):
    vertices: list[VertexFormat5] = field(default_factory=list)


@dataclass
class IndexBuffer(Serializable):
    indices: list[U16] = field(default_factory=list)


@dataclass
class VertexBufferContainer(Serializable):
    vertex_format: U32 = 0
    vertex_buffer: Ptr32 = NULLPTR # VertexBuffer
    vertex_size: U32 = 0
    vertex_count: U32 = 0


@dataclass
class RenderStateType:
    BLEND_MODE = 2
    TEXTURE_ID = 3
    TEXTURE_ADDRESSING = 4
    MATERIAL = 5
    LIGHTING = 6
    TRANSFORM = 7
    MATERIAL_SOURCE = 8


@dataclass
class RenderStateArgs(Serializable):
    state_type: U32 = 0
    arg1: U32 = 0
    arg2: U32 = 0
    unk2: U32 = 0


@dataclass
class IndexBufferContainer(Serializable):
    renderstate_args: Ptr32 = NULLPTR # RenderStateArgs
    renderstate_args_count: U32 = 0
    index_buffer: Ptr32 = NULLPTR # IndexBuffer
    index_count: U32 = 0
    unk1: U32 = 0


@dataclass
class Mesh(Serializable):
    flags: U32 = 0
    vertex_buffers: Ptr32 = NULLPTR # VertexBufferContainer
    vertex_buffer_count: U32 = 0
    index_buffers: Ptr32 = NULLPTR # IndexBufferContainer
    index_buffer_count: U32 = 0
    alpha_index_buffers: Ptr32 = NULLPTR # IndexBufferContainer
    alpha_index_buffer_count: U32 = 0


@dataclass
class MeshTreeNode(Serializable):
    """Guessing the point of this is to have hierarchical transformations"""
    flags: U32 = 0
    mesh: Ptr32 = NULLPTR # Mesh
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    rot_x: I32 = 0
    rot_y: I32 = 0
    rot_z: I32 = 0
    scale_x: F32 = 0.0
    scale_y: F32 = 0.0
    scale_z: F32 = 0.0
    child: Ptr32 = NULLPTR # MeshTreeNode
    next: Ptr32 = NULLPTR # MeshTreeNode


@dataclass
class MeshTree(Serializable):
    root_node: Ptr32 = NULLPTR # MeshTreeNode
    unk1: U32 = 0
    unk2: U32 = 0
    flags: U32 = 0


@dataclass
class Chunk(Serializable):
    """I think chunks might be used for view distance"""
    id: U32 = 0
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    rot_x: I32 = 0
    rot_y: I32 = 0
    rot_z: I32 = 0
    radius: F32 = 0.0
    static_mesh_trees: Ptr32 = NULLPTR # MeshTree
    animated_mesh_trees: Ptr32 = NULLPTR # Unknown
    static_mesh_tree_count: U32 = 0
    animated_mesh_tree_count: U32 = 0
    flags: U32 = 0


class AlignedString(Serializable):
    chars: list[U8] = field(default_factory=list)

    def __init__(self, s: str):
        self.chars = list(str.encode(s))
        self.chars.append(0)

    def serialize_into(self, buf, unused):
        return super().serialize_into(buf, Rel.ALIGNMENT)


@dataclass
class TextureData2(Serializable):
    name: Ptr32 = NULLPTR # AlignedString
    unk1: Ptr32 = NULLPTR # Set at runtime
    data: Ptr32 = NULLPTR # Set at runtime


@dataclass
class TextureData1(Serializable):
    data: Ptr32 = NULLPTR # TextureData2
    data_count: U32 = 0


@dataclass
class NrelFmt2(Serializable):
    magic: list[U8] = util.magic_field("fmt2")
    unk1: U32 = 0
    chunk_count: U16 = 0
    unk2: U16 = 0
    unk3: U32 = 0
    chunks: Ptr32 = NULLPTR # Chunk
    texture_data: Ptr32 = NULLPTR # TextureData1


def make_renderstate_args(texture_id: int, *args, texture_addressing=None, blend_modes=None, lighting=True) -> list[RenderStateArgs]:
    rs_args = [
        RenderStateArgs(
            state_type=RenderStateType.TEXTURE_ID,
            arg1=texture_id)]
    if blend_modes is not None:
        rs_args.append(RenderStateArgs(
            state_type=RenderStateType.BLEND_MODE,
            arg1=blend_modes[0],
            arg2=blend_modes[1]))
    if texture_addressing is not None:
        rs_args.append(RenderStateArgs(
            state_type=RenderStateType.TEXTURE_ADDRESSING,
            arg1=texture_addressing,
            arg2=texture_addressing))
    rs_args.append(RenderStateArgs(
        state_type=RenderStateType.LIGHTING,
        arg1=int(lighting)))
    return rs_args


class NrelError(Exception):
    def __init__(self, msg: str, obj: bpy.types.Object=None):
        s = "N.REL Error"
        if obj:
            s += " in Object '{}'".format(obj.name)
        s += ": " + msg
        super().__init__(s)


def write(nrel_path: str, xvm_path: str, objects: list[bpy.types.Object]):
    rel = Rel()
    nrel = NrelFmt2()
    textures = dict()
    texture_id = -1
    # Put all meshes in one chunk because I don't know how chunks are supposed to work exactly
    nrel.chunk_count = 1
    chunk = Chunk(
        flags=0x00010000,
        static_mesh_tree_count=len(objects))
    farthest_sq = float("-inf")
    static_mesh_trees = []
    # Build mesh tree
    for obj in objects:
        blender_mesh = obj.to_mesh()
        static_mesh_tree = MeshTree(flags=0x00220000)
        mesh_node = MeshTreeNode(flags=0x17, scale_x=1.0, scale_y=1.0, scale_z=1.0)
        tex_image = util.get_object_diffuse_texture(obj)
        geom_center = util.geometry_world_center(obj)
        mesh = Mesh(vertex_buffer_count=1)

        vertex_colors = blender_mesh.color_attributes[0] if len(blender_mesh.color_attributes) > 0 else None
        if vertex_colors:
            # Despite the names of the types, they appear to be identical
            if vertex_colors.data_type != "FLOAT_COLOR" and vertex_colors.data_type != "BYTE_COLOR":
                raise NrelError("Invalid vertex color format '{}'.".format(vertex_colors.data_type), obj)
            if vertex_colors.domain != "CORNER":
                raise NrelError("Invalid vertex color type '{}'. Please select 'Face Corner' when creating color attribute.".format(vertex_colors.domain), obj)
            if len(vertex_colors.data) != len(blender_mesh.loop_triangles) * 3:
                raise NrelError("Vertex color data length mismatch. Remember to triangulate your mesh before painting.", obj)

        if tex_image:
            w, h = tex_image.size
            # If the image file is not found on disk the texture will still exist but without pixels
            if w == 0 or h == 0:
                warn("N.REL Warning: Texture '{}' has no pixels. Does the image file exist on disk?".format(tex_image.filepath))
                tex_image = None
            else:
                # Deduplicate textures
                image_abs_path = tex_image.filepath_from_user()
                if image_abs_path in textures:
                    texture_id = textures[image_abs_path].id
                else:
                    texture_id += 1
                    textures[image_abs_path] = xvm.Texture(id=texture_id, image=tex_image)

        # Vertices. Only one buffer needed.
        # Figure out the right vertex format based on what data mesh has.
        if tex_image:
            if vertex_colors:
                # Coords + color + UVs
                vertex_format = 5
                vertex_size = VertexFormat5.type_size()
                vertex_buffer = VertexBufferFormat5()
                vertex_ctor = VertexFormat5
            else:
                # Coords + UVs
                vertex_format = 1
                vertex_size = VertexFormat1.type_size()
                vertex_buffer = VertexBufferFormat1()
                vertex_ctor = VertexFormat1
        else:
            # Coords + color
            vertex_format = 4
            vertex_size = VertexFormat4.type_size()
            vertex_buffer = VertexBufferFormat4()
            vertex_ctor = VertexFormat4

        faces = []
        vertex_buffer.vertices = [None] * len(blender_mesh.loops)
        # Create vertices. One vertex per loop.
        for face in blender_mesh.loop_triangles:
            faces.append(tuple(face.loops))
            for (vert_idx, loop_idx) in zip(face.vertices, face.loops):
                local_vert = blender_mesh.vertices[vert_idx]
                world_vert = util.from_blender_axes(obj.matrix_world @ local_vert.co)
                farthest_sq = max(farthest_sq, util.distance_squared(geom_center, world_vert))
                vertex = vertex_ctor(
                    x=world_vert[0],
                    y=world_vert[1],
                    z=world_vert[2])
                vertex_buffer.vertices[loop_idx] = vertex
                # Get UVs
                if tex_image:
                    u, v = blender_mesh.uv_layers[0].data[loop_idx].uv
                    vertex.u = u
                    vertex.v = v
                # Get colors
                # Assume faces were triangulated when painting and vertex color array aligns with loops
                if vertex_colors:
                    col = vertex_colors.data[loop_idx].color
                    # BGRA
                    # Need to clamp because light baking can cause values to go higher than normal
                    vertex.diffuse.b = int(util.clamp(col[0], 0.0, 1.0) * 0xff)
                    vertex.diffuse.g = int(util.clamp(col[1], 0.0, 1.0) * 0xff)
                    vertex.diffuse.r = int(util.clamp(col[2], 0.0, 1.0) * 0xff)
                    vertex.diffuse.a = int(util.clamp(col[3], 0.0, 1.0) * 0xff)
        mesh.vertex_buffers = rel.write(VertexBufferContainer(
            vertex_format=vertex_format,
            vertex_buffer=rel.write(vertex_buffer),
            vertex_size=vertex_size,
            vertex_count=len(vertex_buffer.vertices)))

        # Render state args
        rs_arg_count = 0
        first_rs_arg_ptr = NULLPTR
        if tex_image:
            rs_args = make_renderstate_args(
                texture_id,
                blend_modes=(4, 7), # D3DBLEND_SRCALPHA, D3DBLEND_INVSRCALPHA
                texture_addressing=1,  # D3DTADDRESS_MIRROR
                lighting=False) # Map geometry is generally not affected by lighting
            rs_arg_count = len(rs_args)
            for rs_arg in rs_args:
                ptr = rel.write(rs_arg)
                if first_rs_arg_ptr == NULLPTR:
                    first_rs_arg_ptr = ptr

        # Indices. One buffer per strip.
        index_buffer_containers = []
        strips = util.stripify(faces)
        for strip in strips:
            buf_ptr = rel.write(IndexBuffer(indices=strip), True)
            index_buffer_containers.append(IndexBufferContainer(
                index_buffer=buf_ptr,
                index_count=len(strip),
                renderstate_args=first_rs_arg_ptr,
                renderstate_args_count=rs_arg_count))

        # Containers need to be written back to back
        first_index_buffer_container_ptr = None
        for buf in index_buffer_containers:
            ptr = rel.write(buf)
            if first_index_buffer_container_ptr is None:
                first_index_buffer_container_ptr = ptr
        # XXX: Let's just put everything here regardless of if it has alpha or not
        mesh.alpha_index_buffer_count = len(strips)
        mesh.alpha_index_buffers = first_index_buffer_container_ptr

        mesh_node.mesh = rel.write(mesh)
        static_mesh_tree.root_node = rel.write(mesh_node)
        static_mesh_trees.append(static_mesh_tree)
    chunk.radius = math.sqrt(farthest_sq)
    first_static_mesh_tree_ptr = None
    for tree in static_mesh_trees:
        ptr = rel.write(tree)
        if first_static_mesh_tree_ptr is None:
            first_static_mesh_tree_ptr = ptr
    chunk.static_mesh_trees = first_static_mesh_tree_ptr
    nrel.chunks = rel.write(chunk)
    # Texture metadata
    if len(textures) > 0:
        first_texdata2_ptr = NULLPTR
        tex_data1 = TextureData1(data_count=len(textures))
        for tex_path in textures:
            # Create a unique name for the texture without needing to write the entire absolute path in the file
            (dirname, basename) = os.path.split(tex_path)
            tex_name = "tex_" + str(hash(dirname) + sys.maxsize + 1) + "_" + basename
            name_ptr = rel.write(AlignedString(tex_name))
            ptr = rel.write(TextureData2(name=name_ptr))
            if first_texdata2_ptr == NULLPTR:
                first_texdata2_ptr = ptr
        tex_data1.data = first_texdata2_ptr
        nrel.texture_data = rel.write(tex_data1)
    # Write files
    file_contents = rel.finish(rel.write(nrel))
    with open(nrel_path, "wb") as f:
        f.write(file_contents)
    if xvm_path and len(textures) > 0:
        xvm.write(xvm_path, list(textures.values()))
