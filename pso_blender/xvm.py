import os, pathlib, marshal, json, hashlib
from dataclasses import dataclass, field
import bpy
import bpy.types
from .serialization import Serializable, Numeric, ResizableBuffer
from . import dxt
from .util import magic_field, Texture, get_object_diffuse_textures


U8 = Numeric.U8
U16 = Numeric.U16
U32 = Numeric.U32
I8 = Numeric.I8
I16 = Numeric.I16
I32 = Numeric.I32
F32 = Numeric.F32
Ptr32 = Numeric.Ptr32
NULLPTR = Numeric.NULLPTR


class XvrFormat:
    A8R8G8B8 = 1
    R5G6B5 = 2
    A1R5G5B5 = 3
    A4R4G4B4 = 4
    P8 = 5
    DXT1 = 6
    DXT2 = 7
    DXT3 = 8
    DXT4 = 9
    DXT5 = 10
    A8R8G8B8 = 11
    R5G6B5 = 12
    A1R5G5B5 = 13
    A4R4G4B4 = 14
    YUY2 = 15
    V8U8 = 16
    A8 = 17
    X1R5G5B5 = 18
    X8R8G8B8 = 19


class XvrFlags:
    MIPMAPS = 1
    ALPHA = 2


@dataclass
class Xvr(Serializable):
    magic: list[U8] = magic_field("XVRT")
    body_size: U32 = 0
    flags: U32 = 0
    format: U32 = 0
    id: U32 = 0
    width: U16 = 0
    height: U16 = 0
    data_size: U32 = 0
    unk1: U32 = 0
    unk2: U32 = 0
    unk3: U32 = 0
    unk4: U32 = 0
    unk5: U32 = 0
    unk6: U32 = 0
    unk7: U32 = 0
    unk8: U32 = 0
    unk9: U32 = 0
    data: list[U8] = field(default_factory=list)


@dataclass
class Xvm(Serializable):
    magic: list[U8] = magic_field("XVMH")
    body_size: U32 = 0
    xvr_count: U32 = 0
    unk1: U32 = 0
    unk2: U32 = 0
    unk3: U32 = 0
    unk4: U32 = 0
    unk5: U32 = 0
    unk6: U32 = 0
    unk7: U32 = 0
    unk8: U32 = 0
    unk9: U32 = 0
    unk10: U32 = 0
    unk11: U32 = 0
    unk12: U32 = 0
    unk13: U32 = 0
    xvrs: list[Xvr] = field(default_factory=list)


class TextureManager:
    def __init__(self, objects: list[bpy.types.Object]):
        import time
        # Create "unique" texture IDs
        self._base_id = int(time.time()) & 0xffffffff
        id_counter = self._base_id
        # Use file path as an identifier for deduplicating textures
        self._textures_by_path = dict()
        for obj in objects:
            textures = get_object_diffuse_textures(obj)
            for tex in textures:
                w, h = tex.image.size
                # If the image file is not found on disk the texture will still exist but without pixels
                if w == 0 or h == 0 or len(tex.image.pixels) < 1:
                    raise Exception("Error in texture '{}': Texture has no pixels. Does the image file exist on disk?".format(tex.image.filepath))
                else:
                    # Deduplicate textures
                    image_abs_path = tex.image.filepath_from_user()
                    if image_abs_path not in self._textures_by_path:
                        tex.id = id_counter # Assign ID
                        self._textures_by_path[image_abs_path] = tex
                        id_counter += 1

    def get_object_textures(self, obj: bpy.types.Object) -> list[Texture]:
        texture_ids = []
        textures = get_object_diffuse_textures(obj)
        for tex in textures:
            path = tex.image.filepath_from_user()
            if path in self._textures_by_path:
                texture_ids.append(self._textures_by_path[path])
        return texture_ids
    
    def get_all_textures(self) -> list[Texture]:
        return list(self._textures_by_path.values())

    def get_base_id(self) -> int:
        return self._base_id
    
    def has_textures(self) -> bool:
        return len(self._textures_by_path) > 0


def generate_mipmaps(image: bpy.types.Image, has_alpha: bool) -> list[bpy.types.Image]:
    mip_dim, _ = image.size
    levels = []
    level_idx = 0
    alpha_test = 0.75 # Value used by the game

    alpha_test_count = 0
    if has_alpha:
        for px_idx in range(0, len(image.pixels), 4):
            alpha = image.pixels[px_idx + 3]
            if alpha > alpha_test:
                alpha_test_count += 1
    orig_coverage = alpha_test_count / (mip_dim * mip_dim)

    while True:
        level_idx += 1
        mip_dim = mip_dim // 2
        if mip_dim <= 2:
            break
        level = image.copy()
        level.scale(mip_dim, mip_dim)
        if has_alpha:
            alpha_threshold = orig_coverage * alpha_test * mip_dim
            for px_idx in range(0, len(level.pixels), 4):
                alpha = level.pixels[px_idx + 3]
                if alpha > alpha_threshold:
                    level.pixels[px_idx + 3] = 1.0
        levels.append(level)
    return levels


def texture_checksum(tex: Texture) -> str:
    data = list(tex.image.pixels)
    data.append(float(tex.generate_mipmaps))
    return hashlib.md5(marshal.dumps(data)).hexdigest()


def load_cache_index(path: str) -> dict[str, str]:
    if os.path.isfile(path):
        with open(path, "r") as f:
            return json.load(f)
    return dict()


def save_cache_index(path: str, index: dict[str, str]):
    with open(path, "w") as f:
        json.dump(index, f)


def get_cached_xvr(path: str) -> Xvr:
    magic_size = 4
    print("XVM Notice: Loading texture from cache '{}'".format(path))
    with open(path, "rb") as f:
        file_contents = f.read()
        (xvr, offset) = Xvr.deserialize_from(file_contents[magic_size:])
        xvr.data = file_contents[offset + magic_size:]
    return xvr


def cache_xvr(path: str, xvr: Xvr):
    buf = ResizableBuffer(0)
    xvr.serialize_into(buf)
    with open(path, "wb") as f:
        print("XVM Notice: Saving texture to cache '{}'".format(path))
        f.write(buf.buffer)


def make_xvr(tex: Texture) -> Xvr:
    img_width, img_height = tex.image.size
    has_alpha = tex.image.channels == 4
    flags = 0
    if tex.generate_mipmaps:
        flags |= XvrFlags.MIPMAPS
    if has_alpha:
        if tex.image.alpha_mode != "STRAIGHT":
            raise Exception("XVR Error in Image '{}': Image has unsupported alpha mode '{}'".format(tex.image.filepath, tex.image.alpha_mode))
        flags |= XvrFlags.ALPHA
    xvr_format = XvrFormat.DXT1
    data = dxt.compress_image(list(tex.image.pixels), img_width, img_height, tex.image.channels, has_alpha)
    if tex.generate_mipmaps:
        # Concat mipmaps into data
        mipmaps = generate_mipmaps(tex.image, has_alpha)
        for level in mipmaps:
            level_width, level_height = level.size
            data += dxt.compress_image(list(level.pixels), level_width, level_height, level.channels, has_alpha)
            # Remove temporary copies because Blender automatically saves them in the scene
            bpy.data.images.remove(level)
    return Xvr(
        body_size=len(data) + Xvr.type_size() - 4,
        id=tex.id,
        flags=flags,
        format=xvr_format,
        width=img_width,
        height=img_height,
        data_size=len(data),
        data=data)


def write(path: str, textures: list[Texture]):
    # Cache xvr files in a subdirectory inside the destination directory
    cache_dir = "pso-blender-cache"
    xvr_ext = ".xvr"
    (dirname, _) = os.path.split(path)
    # Index contains checksums of files
    cache_index_path = os.path.join(dirname, cache_dir, "index.json")
    cache_index = load_cache_index(cache_index_path)
    xvrs = []
    for tex in textures:
        (_, basename) = os.path.split(tex.image.filepath)
        cache_dir_path = os.path.join(dirname, cache_dir)
        pathlib.Path(cache_dir_path).mkdir(exist_ok=True) # Create dir if not exist
        xvr_basename = basename + xvr_ext
        cached_xvr_path = os.path.join(cache_dir_path, xvr_basename)
        # Try to load cached textures from destination directory if pixels have not changed
        checksum = texture_checksum(tex)
        if os.path.isfile(cached_xvr_path) and checksum == cache_index.get(xvr_basename):
            xvr = get_cached_xvr(cached_xvr_path)
            xvr.id = tex.id # Use new texture id
        else:
            xvr = make_xvr(tex)
            cache_xvr(cached_xvr_path, xvr)
        cache_index[xvr_basename] = checksum
        xvrs.append(xvr)
    save_cache_index(cache_index_path, cache_index)
    buf = ResizableBuffer(0)
    # I'll just explicitly write the lists because it's easier
    xvm = Xvm(
        body_size=Xvm.type_size() - 4,
        xvr_count=len(xvrs))
    xvm.serialize_into(buf)
    for xvr in xvrs:
        data = xvr.data
        xvr.data = []
        xvr.serialize_into(buf)
        buf.append(data)
        buf.seek_to_end()
    with open(path, "wb") as f:
        f.write(buf.buffer)
