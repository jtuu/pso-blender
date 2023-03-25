from dataclasses import dataclass, field
import bpy.types
from .rel import Rel
from .serialization import Serializable, Numeric
from . import util


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
class IndexBufferContainer(Serializable):
    renderstate_args: Ptr32 = NULLPTR # Unknown
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


@dataclass
class NrelFmt2(Serializable):
    magic: list[U8] = field(default_factory=lambda: list(map(ord, "fmt2")))
    unk1: U32 = 0
    chunk_count: U16 = 0
    unk2: U16 = 0
    unk3: U32 = 0
    chunks: Ptr32 = NULLPTR # Chunk
    njtl: Ptr32 = NULLPTR # Unknown


def write(path: str, objects: list[bpy.types.Object]):
    rel = Rel()
    nrel = NrelFmt2()
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

        mesh = Mesh(vertex_buffer_count=1, index_buffer_count=len(strips))

        # Vertices. Only one buffer needed.
        vertex_buffer = VertexBufferFormat4()
        for (i, local_vert) in enumerate(blender_mesh.vertices):
            world_vert = obj.matrix_world @ local_vert.co
            # Add some color to make it easier to see
            r = (i + 10) % 0x7f
            g = (i + 20) % 0x7f
            b = (i + 30) % 0x7f
            # Swap y and z
            vertex_buffer.vertices.append(VertexFormat4(
                x=world_vert[0], y=world_vert[2], z=world_vert[1],
                r=r, g=g, b=b, a=0xff))
        mesh.vertex_buffers = rel.write(VertexBufferContainer(
            vertex_format=4,
            vertex_buffer=rel.write(vertex_buffer),
            vertex_size=VertexFormat4.type_size(),
            vertex_count=len(vertex_buffer.vertices)))
        
        # Indices. One buffer per strip.
        index_buffer_containers = []
        for strip in strips:
            buf_ptr = rel.write(IndexBuffer(indices=strip), True)
            index_buffer_containers.append(IndexBufferContainer(
                index_buffer=buf_ptr,
                index_count=len(strip)))
            
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
    file_contents = rel.finish(rel.write(nrel))
    with open(path, "wb") as f:
        f.write(file_contents)
