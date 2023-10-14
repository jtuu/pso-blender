from dataclasses import dataclass
from .serialization import Serializable, Numeric


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
class MeshTreeNode(Serializable):
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

    @staticmethod
    def read_tree(mesh_type, buf: bytearray, offset: int):
        (node, after) = MeshTreeNode.deserialize_from(buf, offset=offset)
        if node.mesh != NULLPTR:
            node.mesh = mesh_type.deserialize_from(buf, node.mesh)[0]
        if node.child != NULLPTR:
            node.child = MeshTreeNode.deserialize_from(buf, node.child)[0]
        if node.next != NULLPTR:
            node.next = MeshTreeNode.deserialize_from(buf, node.next)[0]
        return (node, after)
