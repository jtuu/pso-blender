import functools, multiprocessing, struct

RGB = tuple[int, int, int]


def rgb8_to_rgb565(rgb: RGB) -> int:
    return ((rgb[0] & 0xf8) << 8) | ((rgb[1] & 0xfc) << 3) | (rgb[2] >> 3)


def decompose_rgb565(rgb: int) -> RGB:
    r = rgb >> 11
    g = (rgb >> 5) & 0x3f
    b = rgb & 0x1f
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def rgb_bounds_of_block(
        pixels: list[float],
        x: int, y: int,
        img_width: int, block_dim: int,
        src_channels: int, dst_channels: int
    ) -> tuple[RGB, RGB]:
    min_rgb8 = [0xff] * dst_channels
    max_rgb8 = [0] * dst_channels
    for block_y in range(block_dim):
        for block_x in range(block_dim):
            src_offset = img_width * ((y + block_y) * src_channels) + ((x + block_x) * src_channels)
            for chan in range(dst_channels):
                val = int(pixels[src_offset + chan] * 0xff)
                if max_rgb8[chan] < val:
                    max_rgb8[chan] = val
                if min_rgb8[chan] > val:
                    min_rgb8[chan] = val
    return (tuple(min_rgb8), tuple(max_rgb8))


def dxt_quantize(min_rgb: RGB, max_rgb: RGB) -> tuple[int, int]:
    inset = tuple(map(lambda a, b: (a - b) >> 4, max_rgb, min_rgb))
    max_rgb565 = rgb8_to_rgb565(tuple(map(lambda a, b: a - b if a >= b else 0, max_rgb, inset)))
    min_rgb565 = rgb8_to_rgb565(tuple(map(lambda a, b: a + b if a + b < 0xff else 0xff, min_rgb, inset)))
    return (min_rgb565, max_rgb565)


def dxt_make_palette(min_rgb565, max_rgb565) -> list[RGB]:
    palette0 = decompose_rgb565(max_rgb565)
    palette1 = decompose_rgb565(min_rgb565)
    palette2 = tuple(map(lambda a, b: (((a << 1) + b) // 3) | 0, palette0, palette1))
    palette3 = tuple(map(lambda a, b: (((b << 1) + a) // 3) | 0, palette0, palette1))
    return [palette0, palette1, palette2, palette3]


def dxt_palettize_block(
        pixels: list[float], palette: list[RGB],
        x: int, y: int,
        img_width: int, block_dim: int,
        src_channels: int, dst_channels: int
    ) -> int:
    palette_indices = 0
    px_idx = 0
    palette_len = len(palette)
    for block_y in range(block_dim):
        for block_x in range(block_dim):
            src_offset = img_width * ((y + block_y) * src_channels) + ((x + block_x) * src_channels)
            best_color_dist = float("inf")
            best_palette_idx = 0
            # Find best palette color for pixel
            for palette_idx in range(palette_len):
                # Compute distance between pixel and palette color
                dist = 0
                for chan in range(dst_channels):
                    val = int(pixels[src_offset + chan] * 0xff)
                    delta = val - palette[palette_idx][chan]
                    dist += delta * delta
                if dist < best_color_dist:
                    best_color_dist = dist
                    best_palette_idx = palette_idx
            # Pack indices
            palette_indices |= best_palette_idx << (px_idx << 1)
            px_idx += 1
    return palette_indices


def dxt1_compress_block(
        pixels: list[float],
        img_width: int, block_dim: int,
        src_channels: int, dst_channels: int,
        coords: tuple[int, int]
    ) -> tuple[int, int, int]:
    # Find RGB bounds of block
    min_rgb8, max_rgb8 = rgb_bounds_of_block(pixels, coords[0], coords[1], img_width, block_dim, src_channels, dst_channels)
    # Quantize
    min_rgb565, max_rgb565 = dxt_quantize(min_rgb8, max_rgb8)
    # Simple write if there is only one color
    if max_rgb565 == min_rgb565:
        palette_indices = 0
        return (min_rgb565, max_rgb565, palette_indices)
    # Fix ordering if it got swapped during quantization
    if max_rgb565 < min_rgb565:
        max_rgb565, min_rgb565 = min_rgb565, max_rgb565
    # Compute palette
    palette = dxt_make_palette(min_rgb565, max_rgb565)
    # Compute pixel palette indices of block
    palette_indices = dxt_palettize_block(pixels, palette, coords[0], coords[1], img_width, block_dim, src_channels, dst_channels)
    return (min_rgb565, max_rgb565, palette_indices)


DXT1_BLOCK_DIM = 4
def dxt1_compress(pixels: list[float], img_width: int, img_height: int, src_channels: int) -> bytearray:
    dst_channels = 3
    if src_channels < dst_channels:
        raise Exception("XVR error: Image must have at least {} channels".format(dst_channels))
    dst_block_size = 2 + 2 + 4
    if img_width % DXT1_BLOCK_DIM != 0 or img_height % DXT1_BLOCK_DIM != 0:
        raise Exception("XVR error: Image dimensions must be multiples of {}".format(DXT1_BLOCK_DIM))
    dst_buf = bytearray(img_width * img_height // dst_block_size * 4)
    # Create work
    block_coords = []
    for y in range(0, img_height, DXT1_BLOCK_DIM):
        for x in range(0, img_width, DXT1_BLOCK_DIM):
            block_coords.append((x, y))
    # Start workers
    worker_fn = functools.partial(dxt1_compress_block, pixels, img_width, DXT1_BLOCK_DIM, src_channels, dst_channels)
    with multiprocessing.Pool() as pool:
        results = pool.map(worker_fn, block_coords)
    # Write results into buffer
    for (block_idx, result) in enumerate(results):
        (min_color, max_color, indices) = result
        dst_offset = block_idx * dst_block_size
        struct.pack_into("<HHL", dst_buf, dst_offset, max_color, min_color, indices)
    return dst_buf
