import functools, multiprocessing, struct


RGB = tuple[int, int, int]


def rgb8_to_rgb565(rgb: RGB) -> int:
    return ((rgb[0] & 0xf8) << 8) | ((rgb[1] & 0xfc) << 3) | (rgb[2] >> 3)


def decompose_rgb565(rgb: int) -> RGB:
    r = rgb >> 11
    g = (rgb >> 5) & 0x3f
    b = rgb & 0x1f
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def dxt_get_block_bounds(
        pixels: list[float],
        x: int, y: int,
        img_width: int, block_dim: int,
        src_channels: int
    ):
    dst_channels = 3
    min_values = [0xff] * dst_channels
    max_values = [0] * dst_channels
    for block_y in range(block_dim):
        for block_x in range(block_dim):
            src_offset = img_width * ((y + block_y) * src_channels) + ((x + block_x) * src_channels)
            for chan in range(dst_channels):
                val = int(pixels[src_offset + chan] * 0xff)
                if max_values[chan] < val:
                    max_values[chan] = val
                if min_values[chan] > val:
                    min_values[chan] = val
    return (min_values, max_values)


def dxt_quantize(min_rgb: RGB, max_rgb: RGB) -> tuple[int, int]:
    inset = tuple(map(lambda a, b: (a - b) >> 4, max_rgb, min_rgb))
    max_rgb565 = rgb8_to_rgb565(tuple(map(lambda a, b: a - b if a >= b else 0, max_rgb, inset)))
    min_rgb565 = rgb8_to_rgb565(tuple(map(lambda a, b: a + b if a + b < 0xff else 0xff, min_rgb, inset)))
    return (min_rgb565, max_rgb565)


def dxt_make_color_palette(color0: int, color1: int) -> list[RGB]:
    palette0 = decompose_rgb565(color0)
    palette1 = decompose_rgb565(color1)
    if color0 <= color1:
        palette2 = tuple(map(lambda a, b: (a + b) // 2, palette0, palette1))
        palette3 = (0, 0, 0, 0)
    else:
        palette2 = tuple(map(lambda a, b: (((a << 1) + b) // 3) | 0, palette0, palette1))
        palette3 = tuple(map(lambda a, b: (((b << 1) + a) // 3) | 0, palette0, palette1))
    return [palette0, palette1, palette2, palette3]


def dxt1_palettize_block(
        pixels: list[float], palette: list[list[int]],
        x: int, y: int,
        img_width: int, block_dim: int,
        src_channels: int,
        with_alpha: int
    ) -> int:
    palette_indices = 0
    px_idx = 0
    palette_len = len(palette)
    for block_y in range(block_dim):
        for block_x in range(block_dim):
            src_offset = img_width * ((y + block_y) * src_channels) + ((x + block_x) * src_channels)
            best_color_dist = float("inf")
            best_palette_idx = 0
            if with_alpha and pixels[src_offset + 3] < 1.0:
                best_palette_idx = 3
            else:
                # Find best palette color for pixel
                for palette_idx in range(palette_len):
                    # Compute distance between pixel and palette color
                    dist = 0
                    for chan in range(3):
                        val = int(pixels[src_offset + chan] * 0xff)
                        delta = val - palette[palette_idx][chan]
                        dist += delta * delta
                    if dist < best_color_dist:
                        best_color_dist = dist
                        best_palette_idx = palette_idx
            # Pack indices
            palette_indices |= best_palette_idx << (px_idx * 2)
            px_idx += 1
    return palette_indices


def dxt1_compress_block(
        pixels: list[float],
        img_width: int, block_dim: int,
        src_channels: int,
        with_alpha: bool,
        coords: tuple[int, int]
    ) -> tuple[int, int, int]:
    # Find RGB bounds of block
    color0, color1 = dxt_get_block_bounds(pixels, coords[0], coords[1], img_width, block_dim, src_channels)
    # Quantize
    color0_565, color1_565 = dxt_quantize(color0, color1)
    if with_alpha:
        if color0_565 > color1_565:
            # Swap colors to indicate alpha format
            color0_565, color1_565 = color1_565, color0_565
    # Colors might get swapped by quantization
    elif color0_565 <= color1_565:
        color0_565, color1_565 = color1_565, color0_565
    # Compute palette
    palette = dxt_make_color_palette(color0_565, color1_565)
    # Compute pixel palette indices of block
    palette_indices = dxt1_palettize_block(pixels, palette[0:3], coords[0], coords[1], img_width, block_dim, src_channels, with_alpha)
    return (color0_565, color1_565, palette_indices)


DXT_BLOCK_DIM = 4
def compress_image(pixels: list[float], img_width: int, img_height: int, src_channels: int, with_alpha: bool) -> bytearray:
    if src_channels < 3 or (with_alpha and src_channels < 4):
        raise Exception("XVR error: Image must have either 3 or 4 channels")
    if img_width % DXT_BLOCK_DIM != 0 or img_height % DXT_BLOCK_DIM != 0:
        raise Exception("XVR error: Image dimensions must be multiples of {}".format(DXT_BLOCK_DIM))
    dst_block_size = 2 + 2 + 4
    dst_buf = bytearray(img_width * img_height // (DXT_BLOCK_DIM * DXT_BLOCK_DIM) * dst_block_size)
    # Create work
    block_coords = []
    for y in range(0, img_height, DXT_BLOCK_DIM):
        for x in range(0, img_width, DXT_BLOCK_DIM):
            block_coords.append((x, y))
    # Start workers
    worker_fn = functools.partial(dxt1_compress_block, pixels, img_width, DXT_BLOCK_DIM, src_channels, with_alpha)
    with multiprocessing.Pool() as pool:
        results = pool.map(worker_fn, block_coords)
    # Write results into buffer
    for (block_idx, result) in enumerate(results):
        dst_offset = block_idx * dst_block_size
        (color0, color1, color_indices) = result
        struct.pack_into("<HHL", dst_buf, dst_offset, color0, color1, color_indices)
    return dst_buf
