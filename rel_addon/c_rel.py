import math
from mathutils import Vector
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
class Vertex(Serializable):
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0

    def __iter__(self):
        return iter([self.x, self.y, self.z])

    def as_vector(self) -> Vector:
        return Vector((self.x, self.y, self.z))


@dataclass
class VertexArray(Serializable):
    vertices: list[Vertex] = field(default_factory=list)


@dataclass
class Face(Serializable):
    index0: U16 = 0
    index1: U16 = 0
    index2: U16 = 0
    flags: U16 = 0
    nx: F32 = 0.0
    ny: F32 = 0.0
    nz: F32 = 0.0
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    radius: F32 = 0.0


@dataclass
class Mesh(Serializable):
    vertex_count: U32 = 0
    vertices: Ptr32 = NULLPTR # VertexArray
    face_count: U32 = 0
    faces: Ptr32 = NULLPTR # Face


class CollisionFlag:
    CAMERA = 0x1
    UNK1 = 0x2
    UNK2 = 0x4
    UNK3 = 0x8
    UNK4 = 0x10
    UNK5 = 0x20
    UNK6 = 0x40
    UNK7 = 0x80
    PROJECTILES = 0x100
    UNK8 = 0x200
    UNK9 = 0x400
    PLAYERS_AND_MONSTERS = 0x800
    UNK10 = 0x1000
    PLAYERS_ONLY = 0x2000
    UNK11 = 0x4000
    MONSTER_VISION = 0x8000


@dataclass
class CrelNode(Serializable):
    mesh: Ptr32 = NULLPTR # Mesh
    x: F32 = 0.0
    y: F32 = 0.0
    z: F32 = 0.0
    radius: F32 = 0.0
    flags: U32 = 0


@dataclass
class Crel(Serializable):
    nodes: Ptr32 = NULLPTR # CrelNode


def write(path: str, objects: list[bpy.types.Object]):
    rel = Rel()
    nodes = []
    for obj in objects:
        blender_mesh = obj.to_mesh()
        vertex_array = VertexArray()
        geom_center = util.from_blender_axes(util.geometry_world_center(obj))

        collision_flags = 0
        if obj.rel_settings.camera_collides:
            collision_flags |= CollisionFlag.CAMERA
        if obj.rel_settings.players_and_monsters_collide:
            collision_flags |= CollisionFlag.PLAYERS_AND_MONSTERS
        if obj.rel_settings.blocks_projectiles:
            collision_flags |= CollisionFlag.PROJECTILES
        if obj.rel_settings.only_players_collide:
            collision_flags |= CollisionFlag.PLAYERS_ONLY
        if obj.rel_settings.blocks_monster_vision:
            collision_flags |= CollisionFlag.MONSTER_VISION
        print(hex(collision_flags))
        node = CrelNode(
            flags=collision_flags,
            x=geom_center[0],
            y=geom_center[1],
            z=geom_center[2])
        farthest_sq = float("-inf")
        # Get vertices and find farthest vertex
        for local_vert in blender_mesh.vertices:
            world_vert = util.from_blender_axes(obj.matrix_world @ local_vert.co)
            farthest_sq = max(farthest_sq, util.distance_squared(geom_center.xz, world_vert.xz))
            vertex_array.vertices.append(Vertex(
                x=world_vert[0], y=world_vert[1], z=world_vert[2]))
        node.radius = math.sqrt(farthest_sq)

        mesh = Mesh(
            vertex_count=len(vertex_array.vertices),
            vertices=rel.write(vertex_array),
            face_count=len(blender_mesh.loop_triangles))

        # Write faces
        first_face_ptr = None
        for face in blender_mesh.loop_triangles:
            # Apply world rotation and scale transforms to normal
            normal = face.normal.to_4d()
            normal.w = 0
            normal = util.from_blender_axes((obj.matrix_world @ normal).to_3d().normalized())
            indices = face.vertices
            # Find farthest distance between vertices
            farthest_sq = float("-inf")
            for i in range(len(face.vertices)):
                for j in range(len(face.vertices)):
                    if i == j:
                        continue
                    a = vertex_array.vertices[i].as_vector().xz
                    b = vertex_array.vertices[j].as_vector().xz
                    farthest_sq = max(farthest_sq, util.distance_squared(a, b))
            center = util.from_blender_axes(obj.matrix_world @ face.center)
            radius = math.sqrt(farthest_sq)
            ptr = rel.write(Face(
                flags=collision_flags,
                x=center[0],
                y=center[1],
                z=center[2],
                index0=indices[0],
                index1=indices[1],
                index2=indices[2],
                radius=radius,
                nx=normal[0],
                ny=normal[1],
                nz=normal[2]))
            if first_face_ptr is None:
                first_face_ptr = ptr
        mesh.faces = first_face_ptr

        node.mesh = rel.write(mesh)
        nodes.append(node)
    nodes.append(CrelNode()) # Terminator
    # Write nodes
    first_node_ptr = None
    for node in nodes:
        ptr = rel.write(node)
        if first_node_ptr is None:
            first_node_ptr = ptr
    file_contents = rel.finish(rel.write(Crel(nodes=first_node_ptr)))
    with open(path, "wb") as f:
        f.write(file_contents)
