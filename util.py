from bpy.types import Mesh

def mesh_faces(mesh: Mesh) -> list[tuple[int, int, int]]:
    """Returns vertex indices of triangulated faces"""
    faces = []
    for poly in mesh.polygons:
        for tri in poly.loop_triangles:
            faces.append(tuple(tri.vertices))
    return faces
