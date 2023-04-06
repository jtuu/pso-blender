import os, math
from mathutils import Vector
from dataclasses import dataclass, field
from warnings import warn
import bpy.types
from .rel import Rel
from .serialization import Serializable, Numeric
from . import util, xvm, tristrip


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


@dataclass
class MeshTreeNode(Serializable):
    """Guessing the point of this is to have hierarchical transformations"""
    eval_flags: U32 = 0
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


class MeshTreeFlag:
    NO_FOG = 0x1
    RECEIVES_SHADOWS = 0x10


@dataclass
class MeshTree(Serializable):
    root_node: Ptr32 = NULLPTR # MeshTreeNode
    unk1: U32 = 0
    unk2: U32 = 0
    tree_flags: U32 = 0


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

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return self.id == other.id

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
    radius: F32 = 0.0 # Overwritten at runtime
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
    def __init__(self, msg: str, *args, obj: bpy.types.Object=None, texture: bpy.types.Image=None):
        s = "N.REL Error"
        if obj:
            s += " in Object '{}'".format(obj.name)
        elif texture:
            s += " in Texture '{}'".format(texture.filepath)
        s += ": " + msg
        super().__init__(s)


def assign_objects_to_chunks(objects: list[bpy.types.Object], chunk_markers: list[bpy.types.Object]) -> dict[Chunk, list[bpy.types.Object]]:
    max_chunk_radius = 1200 # Approximation based on lowest value used by game
    chunk_to_children = dict()
    chunk_flags = 0x00010000
    chunk_counter = 0
    if len(chunk_markers) < 1:
        # No markers, put all meshes in the same chunk at 0,0,0
        warn("N.REL Warning: No chunk markers found in scene. Placing all meshes in default chunk.")
        chunk = Chunk(
            id=chunk_counter,
            flags=chunk_flags,
            static_mesh_tree_count=len(objects),
            x=0.0,
            y=0.0,
            z=0.0)
        chunk_to_children[chunk] = objects
    else:
        # Create a chunk for each marker
        for marker in chunk_markers:
            marker_center = util.from_blender_axes(marker.location)
            chunk = Chunk(
                id=chunk_counter,
                flags=chunk_flags,
                radius=float("-inf"),
                x=marker_center.x,
                y=0.0,
                z=marker_center.z)
            chunk_to_children[chunk] = []
            chunk_counter += 1
        # Find each object's nearest chunk
        for obj in objects:
            obj_center = util.from_blender_axes(util.geometry_world_center(obj))
            nearest_chunk = None
            nearest_dist_sq = float("inf")
            for chunk in chunk_to_children:
                dist_sq = util.distance_squared(obj_center.xz, Vector((chunk.x, 0.0, chunk.z)).xz)
                if dist_sq < nearest_dist_sq:
                    nearest_dist_sq = dist_sq
                    nearest_chunk = chunk
            # Add object to chunk
            chunk_to_children[nearest_chunk].append(obj)
            nearest_chunk.static_mesh_tree_count += 1
            # Also calculate chunk radius. Ensure object is definitely within radius by adding its greatest XZ dimension.
            greatest_obj_dim = max(obj.dimensions.xz)
            radius = math.sqrt(nearest_dist_sq) + greatest_obj_dim
            if radius > nearest_chunk.radius:
                nearest_chunk.radius = radius
                if radius > max_chunk_radius:
                    warn("N.REL Warning: Object '{}' might be too far away from a chunk marker (expected maximum distance of {:.1f}, was {:.1}).".format(
                        obj.name, max_chunk_radius, radius))
        # Discard empty chunks
        for chunk in list(chunk_to_children.keys()):
            if chunk.static_mesh_tree_count < 1:
                del chunk_to_children[chunk]
    return chunk_to_children


def assign_texture_identifiers(objects: list[bpy.types.Object]) -> dict[str, xvm.Texture]:
    textures = dict()
    id_counter = 0
    for obj in objects:
        tex_images = util.get_object_diffuse_textures(obj)
        for tex_image in tex_images:
            w, h = tex_image.size
            # If the image file is not found on disk the texture will still exist but without pixels
            if w == 0 or h == 0 or len(tex_image.pixels) < 1:
                raise NrelError("Texture has no pixels. Does the image file exist on disk?", texture=tex_image)
            else:
                # Deduplicate textures
                image_abs_path = tex_image.filepath_from_user()
                if image_abs_path not in textures:
                    textures[image_abs_path] = xvm.Texture(id=id_counter, image=tex_image)
                    id_counter += 1
    return textures


def get_texture_identifiers(textures: dict[str, xvm.Texture], obj: bpy.types.Object) -> list[int]:
    texture_ids = []
    tex_images = util.get_object_diffuse_textures(obj)
    for tex_image in tex_images:
        texture_ids.append(textures[tex_image.filepath_from_user()].id)
    return texture_ids


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


def write_vertex_buffer(rel: Rel, obj: bpy.types.Object, blender_mesh: bpy.types.Mesh, nrel_mesh: Mesh, has_textures: bool, vertex_colors):
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
                vertex.diffuse.b = int(util.clamp(col[0], 0.0, 1.0) * 0xff)
                vertex.diffuse.g = int(util.clamp(col[1], 0.0, 1.0) * 0xff)
                vertex.diffuse.r = int(util.clamp(col[2], 0.0, 1.0) * 0xff)
                vertex.diffuse.a = int(util.clamp(col[3], 0.0, 1.0) * 0xff)
    # Put all vertices in one buffer
    nrel_mesh.vertex_buffer_count = 1
    nrel_mesh.vertex_buffers = rel.write(VertexBufferContainer(
        vertex_format=vertex_format,
        vertex_buffer=rel.write(vertex_buffer),
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


def write_index_buffers(rel: Rel, nrel_mesh: Mesh, material_strips: list[list[list[int]]], texture_ids: list[int], is_transparent: bool):
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
                    texture_ids[material_idx],
                    blend_modes=blend_modes,
                    texture_addressing=1,  # D3DTADDRESS_MIRROR
                    lighting=False) # Map geometry is generally not affected by lighting
                rs_arg_count = len(rs_args)
                for rs_arg in rs_args:
                    ptr = rel.write(rs_arg)
                    if first_rs_arg_ptr == NULLPTR:
                        first_rs_arg_ptr = ptr
            # Write Indices
            buf_ptr = rel.write(IndexBuffer(indices=strip), True)
            index_buffer_containers.append(IndexBufferContainer(
                index_buffer=buf_ptr,
                index_count=len(strip),
                renderstate_args=first_rs_arg_ptr,
                renderstate_args_count=rs_arg_count))
    # Index buffer containers need to be written back to back
    first_index_buffer_container_ptr = None
    for buf in index_buffer_containers:
        ptr = rel.write(buf)
        if first_index_buffer_container_ptr is None:
            first_index_buffer_container_ptr = ptr
    # XXX: Let's just put everything here regardless of if it has alpha or not
    nrel_mesh.alpha_index_buffer_count = len(index_buffer_containers)
    nrel_mesh.alpha_index_buffers = first_index_buffer_container_ptr


def write(nrel_path: str, xvm_path: str, objects: list[bpy.types.Object], chunk_markers: list[bpy.types.Object]):
    rel = Rel()
    nrel = NrelFmt2()
    textures = assign_texture_identifiers(objects)
    # Create chunks
    chunk_to_children = assign_objects_to_chunks(objects, chunk_markers)
    nrel.chunk_count = len(chunk_to_children)
    # Create chunk data.
    # Chunk coords are world, MeshNodes are local to chunks, mesh vertices are local to MeshNode
    for chunk in chunk_to_children:
        chunk_world_pos = Vector((chunk.x, chunk.y, chunk.z))
        chunk_objects = chunk_to_children[chunk]
        static_mesh_trees = []
        for obj in chunk_objects:
            blender_mesh = obj.to_mesh()
            # One mesh per tree. Create tree, a node, and the mesh.
            tree_flags = 0
            if not obj.rel_settings.receives_fog:
                tree_flags |= MeshTreeFlag.NO_FOG
            if obj.rel_settings.receives_shadows:
                tree_flags |= MeshTreeFlag.RECEIVES_SHADOWS
            static_mesh_tree = MeshTree(tree_flags=tree_flags)

            mesh_world_pos = util.from_blender_axes(obj.location)
            mesh_node = MeshTreeNode(
                eval_flags=NinjaEvalFlag.UNIT_ANG | NinjaEvalFlag.UNIT_SCL | NinjaEvalFlag.BREAK,
                # Make coords relative to chunk
                x=mesh_world_pos.x - chunk_world_pos.x,
                y=mesh_world_pos.y - chunk_world_pos.y,
                z=mesh_world_pos.z - chunk_world_pos.z)
            mesh = Mesh()

            tex_images = util.get_object_diffuse_textures(obj)
            has_textures = len(tex_images) > 0

            vertex_colors = blender_mesh.color_attributes[0] if len(blender_mesh.color_attributes) > 0 else None
            has_vertex_color = bool(vertex_colors)
            if has_vertex_color:
                # Despite the names of the types, they appear to be identical
                if vertex_colors.data_type != "FLOAT_COLOR" and vertex_colors.data_type != "BYTE_COLOR":
                    raise NrelError("Invalid vertex color format '{}'.".format(vertex_colors.data_type), obj=obj)
                if vertex_colors.domain != "CORNER":
                    raise NrelError("Invalid vertex color type '{}'. Please select 'Face Corner' when creating color attribute.".format(vertex_colors.domain), obj=obj)
                if len(vertex_colors.data) != len(blender_mesh.loop_triangles) * 3:
                    raise NrelError("Vertex color data length mismatch. Remember to triangulate your mesh before painting.", obj=obj)
            # Write various mesh data
            texture_ids = get_texture_identifiers(textures, obj)
            write_vertex_buffer(rel, obj, blender_mesh, mesh, has_textures, vertex_colors)
            material_strips = create_tristrips_grouped_by_material(obj, blender_mesh, has_textures)
            write_index_buffers(rel, mesh, material_strips, texture_ids, obj.rel_settings.is_transparent)
            mesh_node.mesh = rel.write(mesh)
            static_mesh_tree.root_node = rel.write(mesh_node)
            static_mesh_trees.append(static_mesh_tree)
        # Write mesh trees back to back
        first_static_mesh_tree_ptr = NULLPTR
        for tree in static_mesh_trees:
            ptr = rel.write(tree)
            if first_static_mesh_tree_ptr == NULLPTR:
                first_static_mesh_tree_ptr = ptr
        chunk.static_mesh_trees = first_static_mesh_tree_ptr
    # Write chunks back to back
    first_chunk_ptr = NULLPTR
    for chunk in chunk_to_children:
        ptr = rel.write(chunk)
        if first_chunk_ptr == NULLPTR:
            first_chunk_ptr = ptr
    nrel.chunks = first_chunk_ptr
    # Texture metadata
    if len(textures) > 0:
        first_texdata2_ptr = NULLPTR
        tex_data1 = TextureData1(data_count=len(textures))
        for tex_path in textures:
            # There might be a limit on the length of these
            (dirname, basename) = os.path.split(tex_path)
            tex_name = basename[0:10]
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
