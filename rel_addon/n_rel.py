from dataclasses import dataclass, field
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
    # Diffuse color
    r: U8 = 0
    g: U8 = 0
    b: U8 = 0
    a: U8 = 0


@dataclass
class VertexBufferFormat1(Serializable):
    vertices: list[VertexFormat1] = field(default_factory=list)


@dataclass
class VertexBufferFormat4(Serializable):
    vertices: list[VertexFormat4] = field(default_factory=list)


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
    unk1: U32 = 0
    unk2: U32 = 0


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


def make_renderstate_args(texture_id: int, *args, texture_addressing=None, blend_modes=None) -> list[RenderStateArgs]:
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
    return rs_args


def write(nrel_path: str, xvm_path: str, objects: list[bpy.types.Object]):
    rel = Rel()
    nrel = NrelFmt2()
    textures = dict()
    texture_id = -1
    # Put all meshes in one chunk because I don't know how chunks are supposed to work exactly
    nrel.chunk_count = 1
    chunk = Chunk(
        flags=0x00010000,
        radius=1000.0,
        static_mesh_tree_count=len(objects))
    static_mesh_trees = []
    # Build mesh tree
    for obj in objects:
        blender_mesh = obj.to_mesh()
        static_mesh_tree = MeshTree(flags=0x00220000)
        mesh_node = MeshTreeNode(flags=0x17, scale_x=1.0, scale_y=1.0, scale_z=1.0)
        faces = util.mesh_faces(blender_mesh)
        strips = util.stripify(faces)
        tex_image = util.get_object_diffuse_texture(obj)

        if tex_image:
            # Deduplicate textures
            image_abs_path = tex_image.filepath_from_user()
            if image_abs_path in textures:
                texture_id = textures[image_abs_path].id
            else:
                texture_id += 1
                textures[image_abs_path] = xvm.Texture(id=texture_id, image=tex_image)

        mesh = Mesh(vertex_buffer_count=1, index_buffer_count=len(strips))

        # Vertices. Only one buffer needed.
        if tex_image:
            # Create vertices with UVs
            vertex_format = 1
            vertex_size = VertexFormat1.type_size()
            vertex_buffer = VertexBufferFormat1()
            for local_vert in blender_mesh.vertices:
                world_vert = util.from_blender_axes(obj.matrix_world @ local_vert.co)
                vertex_buffer.vertices.append(VertexFormat1(
                    x=world_vert[0], y=world_vert[1], z=world_vert[2]))
            # Get UVs
            for tri in blender_mesh.loop_triangles:
                for (vert_idx, loop_idx) in zip(tri.vertices, tri.loops):
                    u, v = blender_mesh.uv_layers[0].data[loop_idx].uv
                    vertex_buffer.vertices[vert_idx].u = u
                    vertex_buffer.vertices[vert_idx].v = v
        else:
            # Create vertices with color
            vertex_format = 4
            vertex_size = VertexFormat4.type_size()
            vertex_buffer = VertexBufferFormat4()
            for (i, local_vert) in enumerate(blender_mesh.vertices):
                world_vert = util.from_blender_axes(obj.matrix_world @ local_vert.co)
                # Add some color to make it easier to see
                r = (i * 10) % 0x7f
                g = (i * 3 + 20) % 0x7f
                b = (i + 30) % 0x7f
                vertex_buffer.vertices.append(VertexFormat4(
                    x=world_vert[0], y=world_vert[1], z=world_vert[2],
                    r=r, g=g, b=b, a=0xff))
        mesh.vertex_buffers = rel.write(VertexBufferContainer(
            vertex_format=vertex_format,
            vertex_buffer=rel.write(vertex_buffer),
            vertex_size=vertex_size,
            vertex_count=len(vertex_buffer.vertices)))
        
        # Render state args
        rs_arg_count = 0
        first_rs_arg_ptr = NULLPTR
        if tex_image:
            rs_args = make_renderstate_args(texture_id)
            rs_arg_count = len(rs_args)
            for rs_arg in rs_args:
                ptr = rel.write(rs_arg)
                if first_rs_arg_ptr == NULLPTR:
                    first_rs_arg_ptr = ptr
        
        # Indices. One buffer per strip.
        index_buffer_containers = []
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
        mesh.index_buffers = first_index_buffer_container_ptr

        mesh_node.mesh = rel.write(mesh)
        static_mesh_tree.root_node = rel.write(mesh_node)
        static_mesh_trees.append(static_mesh_tree)

    first_static_mesh_tree_ptr = None
    for tree in static_mesh_trees:
        ptr = rel.write(tree)
        if first_static_mesh_tree_ptr is None:
            first_static_mesh_tree_ptr = ptr
    chunk.static_mesh_trees = first_static_mesh_tree_ptr
    nrel.chunks = rel.write(chunk)
    # Textures
    first_texdata2_ptr = NULLPTR
    tex_data1 = TextureData1(data_count=len(textures))
    for tex_path in textures:
        name_ptr = rel.write(AlignedString(tex_path))
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
