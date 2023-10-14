import bpy
from dataclasses import dataclass, field
from .serialization import Serializable, Numeric
from struct import unpack_from
from .njcm import MeshTreeNode


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
class VertexFormat3(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    nx: F32 = 0.0
    ny: F32 = 0.0
    nz: F32 = 0.0
    u: F32 = 0.0
    v: F32 = 0.0


@dataclass
class VertexFormat4(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    # Purple default
    r: U8 = 0xff
    g: U8 = 0
    b: U8 = 0xff
    a: U8 = 0xff


@dataclass
class VertexFormat5(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    # Purple default
    r: U8 = 0xff
    g: U8 = 0
    b: U8 = 0xff
    a: U8 = 0xff
    u: F32 = 0.0
    v: F32 = 0.0


@dataclass
class VertexFormat7(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    nx: F32 = 0.0
    ny: F32 = 0.0
    nz: F32 = 0.0
    # Purple default
    r: U8 = 0xff
    g: U8 = 0
    b: U8 = 0xff
    a: U8 = 0xff
    u: F32 = 0.0
    v: F32 = 0.0


@dataclass
class VertexBufferFormat1(Serializable):
    vertices: list[VertexFormat1] = field(default_factory=list)


@dataclass
class VertexBufferFormat3(Serializable):
    vertices: list[VertexFormat3] = field(default_factory=list)


@dataclass
class VertexBufferFormat4(Serializable):
    vertices: list[VertexFormat4] = field(default_factory=list)


@dataclass
class VertexBufferFormat5(Serializable):
    vertices: list[VertexFormat5] = field(default_factory=list)


@dataclass
class VertexBufferFormat7(Serializable):
    vertices: list[VertexFormat7] = field(default_factory=list)


@dataclass
class IndexBuffer(Serializable):
    indices: list[U16] = field(default_factory=list)


@dataclass
class VertexBufferContainer(Serializable):
    vertex_format: U32 = 0
    vertex_buffer: Ptr32 = NULLPTR # VertexBuffer
    vertex_size: U32 = 0
    vertex_count: U32 = 0

    @classmethod
    def deserialize_from(cls, buf, offset):
        (container, after) = super(VertexBufferContainer, cls).deserialize_from(buf, offset)
        if container.vertex_format == 1:
            vert_ctor = VertexFormat1
        elif container.vertex_format == 3:
            vert_ctor = VertexFormat3
        elif container.vertex_format == 4:
            vert_ctor = VertexFormat4
        elif container.vertex_format == 5:
            vert_ctor = VertexFormat5
        elif container.vertex_format == 7:
            vert_ctor = VertexFormat7
        else:
            raise Exception("Unimplemented vertex format {}".format(container.vertex_format))
        container.vertex_buffer = vert_ctor.read_sequence(buf, container.vertex_buffer, container.vertex_count)
        return (container, after)


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

    @classmethod
    def deserialize_from(cls, buf, offset):
        (container, after) = super(IndexBufferContainer, cls).deserialize_from(buf, offset)
        container.renderstate_args = RenderStateArgs.read_sequence(buf, container.renderstate_args, container.renderstate_args_count)
        [endian, typecode] = Numeric.format_of_type(U16)
        fmt = endian + str(container.index_count) + typecode
        container.index_buffer = unpack_from(fmt, buf, offset=container.index_buffer)
        return (container, after)


@dataclass
class Mesh(Serializable):
    flags: U32 = 0
    vertex_buffers: Ptr32 = NULLPTR # VertexBufferContainer
    vertex_buffer_count: U32 = 0
    index_buffers: Ptr32 = NULLPTR # IndexBufferContainer
    index_buffer_count: U32 = 0
    alpha_index_buffers: Ptr32 = NULLPTR # IndexBufferContainer
    alpha_index_buffer_count: U32 = 0

    @classmethod
    def deserialize_from(cls, buf, offset):
        (mesh, after) = super(Mesh, cls).deserialize_from(buf, offset=offset)
        mesh.vertex_buffers = VertexBufferContainer.read_sequence(buf, mesh.vertex_buffers, mesh.vertex_buffer_count)
        mesh.index_buffers = IndexBufferContainer.read_sequence(buf, mesh.index_buffers, mesh.index_buffer_count)
        mesh.alpha_index_buffers = IndexBufferContainer.read_sequence(buf, mesh.alpha_index_buffers, mesh.alpha_index_buffer_count)
        return (mesh, after)


class NinjaEvalFlag:
    UNIT_POS = 0b1 # Ignore translation
    UNIT_ANG = 0b10 # Ignore rotation
    UNIT_SCL = 0b100 # Ignore scaling
    HIDE = 0b1000 # Do not draw model
    BREAK = 0b10000 # Terimnate tracing children
    ZXY_ANG = 0b100000
    SKIP = 0b1000000
    SHAPE_SKIP = 0b10000000
    CLIP = 0b100000000
    MODIFIER = 0b1000000000


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


def xj_to_blender_mesh(name: str, buf: bytearray, offset: int) -> bpy.types.Object:
    (model, _) = MeshTreeNode.read_tree(Mesh, buf, offset)
    if model.mesh == NULLPTR:
        return None

    vertices = []
    faces = []

    for vertex_buffer in model.mesh.vertex_buffers:
        for vertex in vertex_buffer.vertex_buffer:
            vertices.append((vertex.x, vertex.z, vertex.y))

    for index_buffer in model.mesh.index_buffers + model.mesh.alpha_index_buffers:
        indices = index_buffer.index_buffer
        swap = False
        for i in range(len(indices) - 2):
            i0 = indices[i + 0]
            i1 = indices[i + 1]
            i2 = indices[i + 2]
            if swap:
                i1, i2 = i2, i1
            swap = not swap
            faces.append((i0, i1, i2))

    blender_mesh = bpy.data.meshes.new("mesh_" + name)
    blender_mesh.from_pydata(vertices, [], faces)
    blender_mesh.update()
    obj = bpy.data.objects.new(name, blender_mesh)
    return obj
