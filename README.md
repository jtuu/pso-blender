# pso-blender

A Blender plugin that can export the following file formats for Phantasy Star Online Blue Burst:
* **n.rel**: Area map render geometry
* **c.rel**: Area map collision geometry
* **r.rel**: Minimap geometry

Exporting a file with the name `foo.rel` will write three files named `foon.rel`, `fooc.rel`, and `foor.rel`.

To specify which output file a mesh should be exported to, custom **Object Properties** are used to tag meshes.
* `nrel`: n.rel
* `crel`: c.rel
* `rrel`: r.rel

The values of these properties are not used.
Meshes can have multiple tags which will cause them to be exported into each of the specified files.
