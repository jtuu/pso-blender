import bpy
from dataclasses import dataclass, field
from .serialization import Serializable, Numeric
from struct import unpack_from
from .njcm import MeshTreeNode
from . import tristrip, util, xvm


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


def determine_vertex_format(has_textures: bool, has_vertex_colors: bool):
    # Figure out the right vertex format based on what data mesh has.
    if has_textures:
        if has_vertex_colors:
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
    return (vertex_format, vertex_size, vertex_buffer, vertex_ctor)


def write_vertex_buffer(destination: util.AbstractFileArchive, obj: bpy.types.Object, blender_mesh: bpy.types.Mesh, xj_mesh: Mesh, has_textures: bool, vertex_colors):
    # One vertex per loop
    (vertex_format, vertex_size, vertex_buffer, vertex_ctor) = determine_vertex_format(has_textures, bool(vertex_colors))
    vertex_buffer.vertices = [None] * len(blender_mesh.loops)
    for face in blender_mesh.loop_triangles:
        for (vert_idx, loop_idx) in zip(face.vertices, face.loops):
            # Exclude translation from transform
            local_vert = blender_mesh.vertices[vert_idx]
            world_vert = obj.matrix_world @ local_vert.co
            world_vert = local_vert.co.to_4d()
            world_vert.w = 0
            world_vert = util.from_blender_axes((obj.matrix_world @ world_vert).to_3d())
            vertex = vertex_ctor(
                x=world_vert[0],
                y=world_vert[1],
                z=world_vert[2])
            vertex_buffer.vertices[loop_idx] = vertex
            # Get UVs
            if has_textures:
                u, v = blender_mesh.uv_layers[0].data[loop_idx].uv
                vertex.u = u
                vertex.v = v
            # Get colors
            # Assume faces were triangulated when painting and vertex color array aligns with loops
            if vertex_colors:
                col = vertex_colors.data[loop_idx].color
                # BGRA
                # Need to clamp because light baking can cause values to go higher than normal
                vertex.b = int(util.clamp(col[0], 0.0, 1.0) * 0xff)
                vertex.g = int(util.clamp(col[1], 0.0, 1.0) * 0xff)
                vertex.r = int(util.clamp(col[2], 0.0, 1.0) * 0xff)
                vertex.a = int(util.clamp(col[3], 0.0, 1.0) * 0xff)
    # Put all vertices in one buffer
    xj_mesh.vertex_buffer_count = 1
    xj_mesh.vertex_buffers = destination.write(VertexBufferContainer(
        vertex_format=vertex_format,
        vertex_buffer=destination.write(vertex_buffer),
        vertex_size=vertex_size,
        vertex_count=len(vertex_buffer.vertices)))


def create_tristrips_grouped_by_material(obj: bpy.types.Object, blender_mesh: bpy.types.Mesh, has_textures: bool) -> list[list[list[int]]]:
    material_strips = []
    if has_textures:
        material_faces = []
        for i in range(len(obj.material_slots)):
            material_faces.append([])
        for face in blender_mesh.loop_triangles:
            material_faces[face.material_index].append(tuple(face.loops))
        for faces in material_faces:
            strip = tristrip.stripify(faces, stitchstrips=True)
            material_strips.append(strip)
    else:
        faces = []
        for face in blender_mesh.loop_triangles:
            faces.append(tuple(face.loops))
        material_strips.append(tristrip.stripify(faces, stitchstrips=True))
    return material_strips


def write_index_buffers(destination: util.AbstractFileArchive, xj_mesh: Mesh, material_strips: list[list[list[int]]], texture_ids: list[int], is_transparent: bool):
    # One buffer per strip
    index_buffer_containers = []
    for (material_idx, strips) in enumerate(material_strips):
        for strip in strips:
            # Strips can be empty due to unused material slots, skip them
            if len(strip) < 1:
                continue
            # Create render state args
            rs_arg_count = 0
            first_rs_arg_ptr = NULLPTR
            if len(texture_ids) > 0:
                blend_modes = (4, 7) # D3DBLEND_SRCALPHA, D3DBLEND_INVSRCALPHA
                if is_transparent:
                    blend_modes = (4, 1) # D3DBLEND_SRCALPHA, D3DBLEND_ONE
                rs_args = make_renderstate_args(
                    texture_id=texture_ids[material_idx],
                    blend_modes=blend_modes,
                    texture_addressing=1,  # D3DTADDRESS_MIRROR
                    lighting=False) # Map geometry is generally not affected by lighting
                rs_arg_count = len(rs_args)
                for rs_arg in rs_args:
                    ptr = destination.write(rs_arg)
                    if first_rs_arg_ptr == NULLPTR:
                        first_rs_arg_ptr = ptr
            # Write Indices
            buf_ptr = destination.write(IndexBuffer(indices=strip), True)
            index_buffer_containers.append(IndexBufferContainer(
                index_buffer=buf_ptr,
                index_count=len(strip),
                renderstate_args=first_rs_arg_ptr,
                renderstate_args_count=rs_arg_count))
    # Index buffer containers need to be written back to back
    first_index_buffer_container_ptr = None
    for buf in index_buffer_containers:
        ptr = destination.write(buf)
        if first_index_buffer_container_ptr is None:
            first_index_buffer_container_ptr = ptr
    # XXX: Let's just put everything here regardless of if it has alpha or not
    xj_mesh.alpha_index_buffer_count = len(index_buffer_containers)
    xj_mesh.alpha_index_buffers = first_index_buffer_container_ptr


def make_mesh(destination: util.AbstractFileArchive, obj: bpy.types.Object, blender_mesh: bpy.types.Mesh, textures: dict[str, xvm.Texture]) -> Mesh:
    mesh = Mesh()
    tex_images = util.get_object_diffuse_textures(obj)
    has_textures = len(tex_images) > 0

    vertex_colors = blender_mesh.color_attributes[0] if len(blender_mesh.color_attributes) > 0 else None
    has_vertex_color = bool(vertex_colors)
    if has_vertex_color:
        # Despite the names of the types, they appear to be identical
        if vertex_colors.data_type != "FLOAT_COLOR" and vertex_colors.data_type != "BYTE_COLOR":
            raise Exception("XJ error in object '{}': Invalid vertex color format '{}'.".format(obj.name, vertex_colors.data_type))
        if vertex_colors.domain != "CORNER":
            raise Exception("XJ error in object '{}': Invalid vertex color type '{}'. Please select 'Face Corner' when creating color attribute.".format(obj.name, vertex_colors.domain))
        if len(vertex_colors.data) != len(blender_mesh.loop_triangles) * 3:
            raise Exception("XJ error in object '{}': Vertex color data length mismatch. Remember to triangulate your mesh before painting.".format(obj.name))
    # Write various mesh data
    texture_ids = xvm.get_texture_identifiers(textures, obj)
    write_vertex_buffer(destination, obj, blender_mesh, mesh, has_textures, vertex_colors)
    material_strips = create_tristrips_grouped_by_material(obj, blender_mesh, has_textures)
    write_index_buffers(destination, mesh, material_strips, texture_ids, obj.rel_settings.is_transparent)
    return mesh


def make_renderstate_args(*args, texture_id=None, texture_addressing=None, blend_modes=None, lighting=True) -> list[RenderStateArgs]:
    rs_args = []
    if texture_id is not None:
        rs_args.append(RenderStateArgs(
            state_type=RenderStateType.TEXTURE_ID,
            arg1=texture_id))
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
