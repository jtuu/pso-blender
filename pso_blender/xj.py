import bpy, os
from dataclasses import dataclass, field
from .serialization import Serializable, Numeric, AlignedString
from struct import unpack_from, pack_into
from .njcm import MeshTreeNode
from . import tristrip, util, xvm
from .iff import IffHeader, IffChunk, parse_pof0
from .njtl import TextureList, TextureListEntry


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
class BlendMode:
    # Not the actual d3d enum values, but indices into an array containing the enum values
    D3DBLEND_ZERO = 0
    D3DBLEND_ONE = 1
    D3DBLEND_SRCCOLOR = 2
    D3DBLEND_SRCALPHA = 3
    D3DBLEND_SRCALPHA = 4
    D3DBLEND_INVSRCALPHA = 5
    D3DBLEND_DESTALPHA = 6
    D3DBLEND_INVDESTALPHA = 7
    D3DBLEND_DESTCOLOR = 8
    D3DBLEND_INVDESTCOLOR = 9


@dataclass
class TextureAddressingMode:
    D3DTADDRESS_WRAP = 3
    D3DTADDRESS_MIRROR = 4
    D3DTADDRESS_CLAMP = 5
    D3DTADDRESS_BORDER = 6
    D3DTADDRESS_MIRRORONCE = 7


@dataclass
class MaterialColorSource:
    D3DMCS_MATERIAL = 0
    D3DMCS_COLOR1 = 1
    D3DMCS_COLOR2 = 3


@dataclass
class RenderStateType:
    BLEND_MODE = 2
    TEXTURE_ID = 3
    TEXTURE_ADDRESSING = 4
    MATERIAL = 5
    LIGHTING = 6
    CAMERA_SPACE_NORMALS = 7
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
            if vertex_colors:
                # Assuming vertex colors are "face corner" type, i.e. per-loop
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


class MaterialStrips:
    def __init__(self, material_index: int, material: bpy.types.Material, strips: list[list[int]]):
        self.material_index = material_index
        self.renderstate_args = make_renderstate_args(
            blend_modes=(material.xj_settings.src_blend, material.xj_settings.dst_blend),
            texture_addressing=(material.xj_settings.tex_addr_u, material.xj_settings.tex_addr_v),
            lighting=material.xj_settings.lighting,
            material=(material.xj_settings.material1, material.xj_settings.material2),
            camera_space_normals=material.xj_settings.camera_space_normals,
            diffuse_color_source=material.xj_settings.diffuse_color_source)
        self.strips = strips


def create_tristrips_grouped_by_material(obj: bpy.types.Object, blender_mesh: bpy.types.Mesh, texture_man: xvm.TextureManager) -> list[MaterialStrips]:
    material_strips = []
    if texture_man.has_textures():
        material_faces = []
        for (mat_idx, mat_slot) in enumerate(obj.material_slots):
            material_faces.append([])
            material_strips.append(MaterialStrips(mat_idx, mat_slot.material, []))
        for face in blender_mesh.loop_triangles:
            material_faces[face.material_index].append(tuple(face.loops))
        for mat_idx in range(len(obj.material_slots)):
            strips = tristrip.stripify(material_faces[mat_idx], stitchstrips=True)
            material_strips[mat_idx].strips = strips
    else:
        faces = []
        for face in blender_mesh.loop_triangles:
            faces.append(tuple(face.loops))
        material_strips.append(tristrip.stripify(faces, stitchstrips=True))
    return material_strips


def write_index_buffers(destination: util.AbstractFileArchive, obj: bpy.types.Object, blender_mesh: bpy.types.Mesh, xj_mesh: Mesh, texture_man: xvm.TextureManager, has_vertex_alpha: bool):
    # Texture IDs must be 0-based for the render settings
    # One buffer per strip
    material_strips = create_tristrips_grouped_by_material(obj, blender_mesh, texture_man)
    opaque_index_buffer_containers = []
    alpha_index_buffer_containers = []
    textures = texture_man.get_object_textures(obj)
    texture_id_base = texture_man.get_base_id()
    for material_strip_data in material_strips:
        for strip in material_strip_data.strips:
            # Strips can be empty due to unused material slots, skip them
            if len(strip) < 1:
                continue
            has_alpha = has_vertex_alpha
            # Create render state args
            first_rs_arg_ptr = NULLPTR
            rs_args = material_strip_data.renderstate_args
            if texture_man.has_textures():
                tex = textures[material_strip_data.material_index]
                has_alpha = has_alpha or tex.has_alpha
                rs_args += make_renderstate_args(
                    # XXX: Assumes material index matches index of texture in this array
                    texture_id=tex.id - texture_id_base)
            rs_arg_count = len(rs_args)
            for rs_arg in rs_args:
                ptr = destination.write(rs_arg)
                if first_rs_arg_ptr == NULLPTR:
                    first_rs_arg_ptr = ptr
            # Write Indices
            buf_ptr = destination.write(IndexBuffer(indices=strip), True)
            containers = alpha_index_buffer_containers if has_alpha else opaque_index_buffer_containers
            containers.append(IndexBufferContainer(
                index_buffer=buf_ptr,
                index_count=len(strip),
                renderstate_args=first_rs_arg_ptr,
                renderstate_args_count=rs_arg_count))
    # Index buffer containers need to be written back to back
    first_alpha_index_buffer_container_ptr = NULLPTR
    for buf in alpha_index_buffer_containers:
        ptr = destination.write(buf)
        if first_alpha_index_buffer_container_ptr == NULLPTR:
            first_alpha_index_buffer_container_ptr = ptr
    first_opaque_index_buffer_container_ptr = NULLPTR
    for buf in opaque_index_buffer_containers:
        ptr = destination.write(buf)
        if first_opaque_index_buffer_container_ptr == NULLPTR:
            first_opaque_index_buffer_container_ptr = ptr
    xj_mesh.alpha_index_buffer_count = len(alpha_index_buffer_containers)
    xj_mesh.alpha_index_buffers = first_alpha_index_buffer_container_ptr
    xj_mesh.index_buffer_count = len(opaque_index_buffer_containers)
    xj_mesh.index_buffers = first_opaque_index_buffer_container_ptr


def make_mesh(destination: util.AbstractFileArchive, obj: bpy.types.Object, blender_mesh: bpy.types.Mesh, texture_man: xvm.TextureManager) -> Mesh:
    mesh = Mesh()

    vertex_colors = blender_mesh.color_attributes[0] if len(blender_mesh.color_attributes) > 0 else None
    has_vertex_color = bool(vertex_colors)
    has_vertex_alpha = False
    if has_vertex_color:
        # Despite the names of the types, they appear to be identical
        if vertex_colors.data_type != "FLOAT_COLOR" and vertex_colors.data_type != "BYTE_COLOR":
            raise Exception("XJ error in object '{}': Invalid vertex color format '{}'.".format(obj.name, vertex_colors.data_type))
        if vertex_colors.domain != "CORNER":
            raise Exception("XJ error in object '{}': Invalid vertex color type '{}'. Please select 'Face Corner' when creating color attribute.".format(obj.name, vertex_colors.domain))
        for attr in vertex_colors.data:
            if attr.color[3] < 1:
                has_vertex_alpha = True
                break
    # Write various mesh data
    write_vertex_buffer(destination, obj, blender_mesh, mesh, texture_man.has_textures(), vertex_colors)
    write_index_buffers(destination, obj, blender_mesh, mesh, texture_man, has_vertex_alpha)
    return mesh


def make_renderstate_args(
    *args,
    texture_id=None,
    texture_addressing=None,
    blend_modes=None,
    lighting=None,
    material=None,
    camera_space_normals=None,
    diffuse_color_source=None
) -> list[RenderStateArgs]:
    rs_args = []
    if texture_id is not None:
        rs_args.append(RenderStateArgs(
            state_type=RenderStateType.TEXTURE_ID,
            arg1=texture_id))
    if texture_addressing is not None:
        rs_args.append(RenderStateArgs(
            state_type=RenderStateType.TEXTURE_ADDRESSING,
            arg1=int(texture_addressing[0]),
            arg2=int(texture_addressing[1])))
    if blend_modes is not None:
        rs_args.append(RenderStateArgs(
            state_type=RenderStateType.BLEND_MODE,
            arg1=int(blend_modes[0]),
            arg2=int(blend_modes[1])))
    if lighting is not None:
        rs_args.append(RenderStateArgs(
            state_type=RenderStateType.LIGHTING,
            arg1=int(lighting)))
    if material is not None:
        rs_args.append(RenderStateArgs(
            state_type=RenderStateType.MATERIAL,
            arg1=int(material[0]),
            arg2=int(material[1])))
    if camera_space_normals is not None:
        rs_args.append(RenderStateArgs(
            state_type=RenderStateType.CAMERA_SPACE_NORMALS,
            arg1=int(camera_space_normals)))
    if diffuse_color_source is not None:
        rs_args.append(RenderStateArgs(
            state_type=RenderStateType.MATERIAL_SOURCE,
            arg1=int(diffuse_color_source)))
    return rs_args


def xj_to_blender_mesh(name: str, buf: bytearray, offset: int) -> bpy.types.Collection:
    (model, _) = MeshTreeNode.read_tree(Mesh, buf, offset)
    collection = bpy.data.collections.new(name)

    # Find all meshes in model tree
    search_stack = [model]
    while len(search_stack) > 0:
        model = search_stack.pop()

        if model == NULLPTR:
            continue
        
        # Search children and siblings
        search_stack.append(model.child)
        search_stack.append(model.next)

        if model.mesh == NULLPTR:
            continue

        vertices = []
        faces = []

        # Get vertices
        for vertex_buffer in model.mesh.vertex_buffers:
            for vertex in vertex_buffer.vertex_buffer:
                vertices.append((vertex.x, vertex.z, vertex.y))

        # Get indices
        for index_buffer in model.mesh.index_buffers + model.mesh.alpha_index_buffers:
            indices = index_buffer.index_buffer
            swap = False
            for i in range(len(indices) - 2):
                # Parsing a triangle strip
                i0 = indices[i + 0]
                i1 = indices[i + 1]
                i2 = indices[i + 2]
                if swap:
                    i1, i2 = i2, i1
                swap = not swap
                faces.append((i0, i1, i2))

        # Put geometry into blender object
        blender_mesh = bpy.data.meshes.new("mesh_" + name)
        blender_mesh.from_pydata(vertices, [], faces)
        blender_mesh.update()
        obj = bpy.data.objects.new(name, blender_mesh)
        collection.objects.link(obj)
    return collection


def write(xj_path: str, xvm_path: str, obj: bpy.types.Object):
    texture_man = xvm.TextureManager([obj])
    textures = texture_man.get_object_textures(obj)

    njcm_chunk = IffChunk("NJCM")
    # Root node must to be the first thing after the chunk header
    mesh_node = MeshTreeNode(
        eval_flags=NinjaEvalFlag.UNIT_ANG | NinjaEvalFlag.UNIT_SCL | NinjaEvalFlag.BREAK,
        mesh=0xdeadbeef, # Will be rewritten at the end
        scale_x=1.0,
        scale_y=1.0,
        scale_z=1.0)
    mesh_pointer_offset = njcm_chunk.write(mesh_node) + IffHeader.type_size() + 4

    blender_mesh = obj.to_mesh()
    util.scale_mesh(blender_mesh, util.get_pso_world_scale())
    mesh = make_mesh(njcm_chunk, obj, blender_mesh, texture_man)

    # Write mesh pointer into root node
    mesh_ptr = njcm_chunk.write(mesh)
    pack_into("<L", njcm_chunk.buf.buffer, mesh_pointer_offset, mesh_ptr)

    # Chunk (+POF0) is done
    xj_buf = njcm_chunk.finish()

    if len(textures) > 0:
        # Make NJTL chunk (doesn't contain pixel data)
        njtl_chunk = IffChunk("NJTL")
        texlist = TextureList(
            elements=0xdeadbeef,
            count=len(textures))
        texlist_elements_offset = njtl_chunk.write(texlist) + IffHeader.type_size()

        first_texlist_entry_ptr = NULLPTR
        for texture in textures:
            tex_name = texture.image.name[0:31]
            name_ptr = njtl_chunk.write(AlignedString(tex_name, IffChunk.ALIGNMENT))
            ptr = njtl_chunk.write(TextureListEntry(name=name_ptr))
            if first_texlist_entry_ptr == NULLPTR:
                first_texlist_entry_ptr = ptr
        # Rewrite pointer
        pack_into("<L", njtl_chunk.buf.buffer, texlist_elements_offset, first_texlist_entry_ptr)

        # Append NJTL
        xj_buf += njtl_chunk.finish()
    
    obj.to_mesh_clear()

    with open(xj_path, "wb") as f:
        f.write(xj_buf)

    if xvm_path and texture_man.has_textures():
        xvm.write(xvm_path, textures)


def read(path: str) -> list[bpy.types.Collection]:
    filename = os.path.basename(path)
    collections = []
    chunk_header_size = IffHeader.type_size()

    with open(path, "rb") as f:
        file_contents = bytearray(f.read())

    # Read iff chunks
    chunk_offset = 0
    prev_chunk_offset = None
    prev_chunk_size = None
    need_pof0 = False
    while chunk_offset < len(file_contents):
        (chunk_header, _) = IffHeader.deserialize_from(file_contents, offset=chunk_offset)
        chunk_type = util.bytes_to_string(chunk_header.type_name)
        if chunk_type == "NJCM":
            need_pof0 = True
        elif chunk_type == "POF0":
            if need_pof0:
                # Could maybe check if pointers to 0 are valid?
                _ = parse_pof0(filename, file_contents, prev_chunk_offset, prev_chunk_size, chunk_offset, chunk_header.body_size)
                # Read a NJCM
                collections.append(xj_to_blender_mesh(filename, file_contents[prev_chunk_offset + chunk_header_size:], 0))
                need_pof0 = False
        prev_chunk_offset = chunk_offset
        prev_chunk_size = chunk_header.body_size
        chunk_offset += chunk_header.body_size + chunk_header_size
    return collections
