import bpy, warnings
from dataclasses import dataclass, field
from .serialization import Serializable, Numeric
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
class Vertex(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    nx: F32 = 0.0
    ny: F32 = 0.0
    nz: F32 = 0.0


@dataclass
class VertexListNode(Serializable):
    flags: U16 = 0 # 0xff=terminator
    # Offset to next VertexListNode, BUT divided by four
    offset_to_next: U16 = 0
    unk1: U16 = 0
    vertex_count: U16 = 0
    vertices: list[Vertex] = field(default_factory=list)


@dataclass
class IndexArray(Serializable):
    length: U16 = 0
    indices: list[U16] = field(default_factory=list)


@dataclass
class IndexListNode(Serializable):
    flags: U16 = 0
    # Offset to next IndexListNode, BUT divided by two
    offset_to_next: U16 = 0
    strip_count: U16 = 0
    indices: list[IndexArray] = field(default_factory=lambda: [IndexArray(length=0)])


@dataclass
class Mesh(Serializable):
    vertex_list: Ptr32 = NULLPTR # VertexListNode
    index_list: Ptr32 = NULLPTR # IndexListNode
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0

    @classmethod
    def deserialize_from(cls, buf, offset):
        (mesh, after) = super(Mesh, cls).deserialize_from(buf, offset)
        vertex_list_offset = mesh.vertex_list - offset
        mesh.vertex_list = []
        while True:
            (vertex_buffer, vertex_array_offset) = VertexListNode.deserialize_from(buf, vertex_list_offset)
            if vertex_buffer.flags == 0xff:
                break
            vertex_format = (vertex_buffer.flags & 0xff) - 0x20
            print(vertex_buffer)
            break
            mesh.vertex_list.append(vertex_buffer)
            vertex_list_offset += vertex_buffer.offset_to_next * 2
        index_list_offset = mesh.index_list
        mesh.index_list = []
        return (mesh, after)


def nj_to_blender_mesh(name: str, buf: bytearray, offset: int) -> bpy.types.Collection:
    (model, _) = MeshTreeNode.read_tree(Mesh, buf, offset)
    if model.mesh == NULLPTR:
        return None
    collection = bpy.data.collections.new(name)
    warnings.warn("BML/NJ import is unimplemented")
    return collection
