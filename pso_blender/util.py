import math
from mathutils import Vector
import bpy.types 
from dataclasses import field


def mesh_faces(mesh: bpy.types.Mesh) -> list[tuple[int, int, int]]:
    """Returns vertex indices of triangulated faces"""
    faces = []
    for tri in mesh.loop_triangles:
        faces.append(tuple(tri.vertices))
    return faces


def get_object_diffuse_textures(obj: bpy.types.Object) -> list[bpy.types.Image]:
    """Assumes the first image node of each material is the correct one"""
    textures = []
    for mat_slot in obj.material_slots:
        if not mat_slot.material or not mat_slot.material.node_tree:
            continue
        for node in mat_slot.material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                textures.append(node.image)
                break
    return textures


def magic_bytes(s: str) -> list[int]:
    return list(map(ord, s))


def magic_field(s: str):
    return field(default_factory=lambda: magic_bytes(s))


def from_blender_axes(tup, invert_z=True) -> Vector:
    """Swaps second and third component"""
    x, z, y = tup
    if invert_z:
        z *= -1
    return Vector((x, y, z))


def distance_squared(a, b) -> float:
    return sum(map(lambda a_, b_: (b_ - a_) ** 2, a, b))


def distance(a, b) -> float:
    return math.sqrt(distance_squared(a, b))


def geometry_world_center(obj: bpy.types.Object) -> Vector:
    local = 1 / 8 * sum((Vector(corner) for corner in obj.bound_box), Vector())
    return obj.matrix_world @ local


def clamp(n, min_val, max_val):
    return max(min(n, max_val), min_val)
