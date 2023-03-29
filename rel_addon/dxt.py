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
        src_channels: int,
        select_channels: list[int]
    ):
    min_values = [0xff] * 4
    max_values = [0] * 4
    for block_y in range(block_dim):
        for block_x in range(block_dim):
            src_offset = img_width * ((y + block_y) * src_channels) + ((x + block_x) * src_channels)
            for chan in select_channels:
                val = int(pixels[src_offset + chan] * 0xff)
                if max_values[chan] < val:
                    max_values[chan] = val
                if min_values[chan] > val:
                    min_values[chan] = val
    min_result = []
    max_result = []
    for chan in select_channels:
        min_result.append(min_values[chan])
        max_result.append(max_values[chan])
    return (tuple(min_result), tuple(max_result))


def dxt_quantize(min_rgb: RGB, max_rgb: RGB) -> tuple[int, int]:
    inset = tuple(map(lambda a, b: (a - b) >> 4, max_rgb, min_rgb))
    max_rgb565 = rgb8_to_rgb565(tuple(map(lambda a, b: a - b if a >= b else 0, max_rgb, inset)))
    min_rgb565 = rgb8_to_rgb565(tuple(map(lambda a, b: a + b if a + b < 0xff else 0xff, min_rgb, inset)))
    return (min_rgb565, max_rgb565)


def dxt_make_color_palette(min_rgb565: int, max_rgb565: int) -> list[RGB]:
    palette0 = decompose_rgb565(max_rgb565)
    palette1 = decompose_rgb565(min_rgb565)
    palette2 = tuple(map(lambda a, b: (((a << 1) + b) // 3) | 0, palette0, palette1))
    palette3 = tuple(map(lambda a, b: (((b << 1) + a) // 3) | 0, palette0, palette1))
    return [palette0, palette1, palette2, palette3]


def dxt5_make_alpha_palette(a0: int, a1: int) -> list[int]:
    palette = [a0, a1]
    if a0 <= a1:
        count = 4
    else:
        count = 6
    for i in range(count):
        val = int(((count - i) * a0 + (i + 1) * a1) / (count + 1))
        palette.append(val)
    if a0 <= a1:
        palette.append(0)
        palette.append(0xff)
    for i in range(len(palette)):
        # Match channel index
        palette[i] = (0, 0, 0, palette[i])
    return palette


def dxt_palettize_block(
        pixels: list[float], palette: list[list[int]],
        x: int, y: int,
        img_width: int, block_dim: int,
        src_channels: int,
        select_channels: list[int],
        index_size: int
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
                for chan in select_channels:
                    val = int(pixels[src_offset + chan] * 0xff)
                    delta = val - palette[palette_idx][chan]
                    dist += delta * delta
                if dist < best_color_dist:
                    best_color_dist = dist
                    best_palette_idx = palette_idx
            # Pack indices
            palette_indices |= best_palette_idx << (px_idx * index_size)
            px_idx += 1
    return palette_indices


def dxt1_compress_block(
        pixels: list[float],
        img_width: int, block_dim: int,
        src_channels: int,
        coords: tuple[int, int]
    ) -> tuple[int, int, int]:
    # Find RGB bounds of block
    min_rgb8, max_rgb8 = dxt_get_block_bounds(pixels, coords[0], coords[1], img_width, block_dim, src_channels, [0, 1, 2])
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
    palette = dxt_make_color_palette(min_rgb565, max_rgb565)
    # Compute pixel palette indices of block
    palette_indices = dxt_palettize_block(pixels, palette, coords[0], coords[1], img_width, block_dim, src_channels, [0, 1, 2], 2)
    return (min_rgb565, max_rgb565, palette_indices)


def dxt5_compress_block_alpha(
        pixels: list[float],
        img_width: int, block_dim: int,
        src_channels: int,
        coords: tuple[int, int]
    ) -> tuple[int, int, int]:
    ((a0,), (a1,)) = dxt_get_block_bounds(pixels, coords[0], coords[1], img_width, block_dim, src_channels, [3])
    if a0 == a1:
        palette_indices = 0
        return (a0, a1, palette_indices)
    # Enable larger palette if we already have one of the extreme values
    # Larger palette is used when a0 > a1 which can be achieved by swapping the values
    if a0 == 0 or a1 == 0xff:
        a0, a1 = a1, a0
    palette = dxt5_make_alpha_palette(a0, a1)
    palette_indices = dxt_palettize_block(pixels, palette, coords[0], coords[1], img_width, block_dim, src_channels, [3], 3)
    return (a0, a1, palette_indices)


def dxt_compress_block(
        pixels: list[float],
        img_width: int, block_dim: int,
        src_channels: int,
        with_alpha: bool,
        coords: tuple[int, int]):
    color_result = dxt1_compress_block(pixels, img_width, block_dim, src_channels, coords)
    if with_alpha:
        alpha_result = dxt5_compress_block_alpha(pixels, img_width, block_dim, src_channels, coords)
        return (color_result, alpha_result)
    return (color_result,)


DXT_BLOCK_DIM = 4
def compress_image(pixels: list[float], img_width: int, img_height: int, src_channels: int, with_alpha: bool) -> bytearray:
    if src_channels < 3 or (with_alpha and src_channels < 4):
        raise Exception("XVR error: Image must have either 3 or 4 channels")
    if img_width % DXT_BLOCK_DIM != 0 or img_height % DXT_BLOCK_DIM != 0:
        raise Exception("XVR error: Image dimensions must be multiples of {}".format(DXT_BLOCK_DIM))
    if with_alpha:
        dst_block_size = 2 + 2 + 4 + 8
    else:
        dst_block_size = 2 + 2 + 4
    dst_buf = bytearray(img_width * img_height // (DXT_BLOCK_DIM * DXT_BLOCK_DIM) * dst_block_size)
    # Create work
    block_coords = []
    for y in range(0, img_height, DXT_BLOCK_DIM):
        for x in range(0, img_width, DXT_BLOCK_DIM):
            block_coords.append((x, y))
    # Start workers
    worker_fn = functools.partial(dxt_compress_block, pixels, img_width, DXT_BLOCK_DIM, src_channels, with_alpha)
    with multiprocessing.Pool() as pool:
        results = pool.map(worker_fn, block_coords)
    # Write results into buffer
    for (block_idx, result) in enumerate(results):
        dst_offset = block_idx * dst_block_size
        if with_alpha:
            alpha_result = result[1]
            (alpha0, alpha1, alpha_indices) = alpha_result
            # Can't write a 48bit value with pack_into so let's just pack it all into a 64bit value
            alpha_packed = ((alpha_indices << 16) | (alpha1 << 8)) | alpha0
            struct.pack_into("<Q", dst_buf, dst_offset, alpha_packed)
            dst_offset += 8
        color_result = result[0]
        (color0, color1, color_indices) = color_result
        # Reverse order of colors indicates DXT1 without alpha, which is also correct for DXT5 with alpha
        struct.pack_into("<HHL", dst_buf, dst_offset, color1, color0, color_indices)
    return dst_buf


def dxt1_compress_image(pixels: list[float], img_width: int, img_height: int) -> bytearray:
    return compress_image(pixels, img_width, img_height, 3, False)


def dxt5_compress_image(pixels: list[float], img_width: int, img_height: int) -> bytearray:
    return compress_image(pixels, img_width, img_height, 4, True)
