import math
from mathutils import Vector, Matrix
import bpy.types 
from dataclasses import field
from abc import ABC, abstractmethod
from .serialization import Serializable


def mesh_faces(mesh: bpy.types.Mesh) -> list[tuple[int, int, int]]:
    """Returns vertex indices of triangulated faces"""
    faces = []
    for tri in mesh.loop_triangles:
        faces.append(tuple(tri.vertices))
    return faces


class Texture:
    id: int
    generate_mipmaps: bool
    has_alpha: bool
    image: bpy.types.Image
    animation_frames: int

    def __init__(self, *args, id: int=None, image: bpy.types.Image, generate_mipmaps: bool=False, animation_frames: int=0):
        self.id = id
        self.image = image
        self.generate_mipmaps = generate_mipmaps
        self.animation_frames = animation_frames
        # Check if texture uses alpha
        self.has_alpha = image.channels == 4
        if self.has_alpha:
            pixels = list(image.pixels)
            self.has_alpha = False
            for i in range(0, len(pixels), 4):
                if pixels[i + 3] < 1:
                    self.has_alpha = True
                    break


def get_object_diffuse_textures(obj: bpy.types.Object) -> list[Texture]:
    """Assumes the first image node of each material is the correct one"""
    textures = []
    for mat_slot in obj.material_slots:
        if not mat_slot.material or not mat_slot.material.node_tree:
            continue
        for node in mat_slot.material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                textures.append(Texture(generate_mipmaps=mat_slot.material.xj_settings.generate_mipmaps, image=node.image))
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


class AbstractFileArchive(ABC):
    @abstractmethod
    def write(self, item: Serializable, ensure_aligned=False) -> int:
        pass


def bytes_to_string(b: list[int]) -> str:
    return bytes(b).decode().rstrip("\0")


def align_up(n: int, to: int) -> int:
    return (n + to - 1) // to * to


def scale_mesh(mesh: bpy.types.Mesh, x: float, y: float=None, z: float=None):
    if y is None:
        y = x
    if z is None:
        z = x
    mesh.transform(Matrix.LocRotScale(None, None, Vector((x, y, z))))


def get_pso_world_scale() -> float:
    return 33.0
