#!/usr/bin/env python3

"""Compare two images

Equivalent to

    compare IMAGE1 IMAGE2 png:- \
        | montage -geometry +4+4 IMAGE1 - IMAGE2 png:-
"""

import argparse
import sys

from PIL import Image, ImageChops, ImageMath, ImageOps


def diff(im1: Image.Image, im2: Image.Image) -> Image.Image:
    assert im1.size == im2.size, "image sizes differ"

    im1 = im1.convert("RGB")
    im2 = im2.convert("RGB")

    size = im1.size
    montage_size = (3 * size[0] + 2 * 3 * 4, size[1] + 2 * 4)

    compare = Image.blend(
        im1,
        ImageChops.add(
            ImageChops.difference(im1, im2).point(lambda px: 0 if px > 0 else 255),
            Image.new("RGB", size, color="#f1001e")
        ),
        0.8
    )

    montage = Image.new("RGB", montage_size, color="white")

    def box(pos, border=(4, 4)) -> "tuple[int, int]":
        return (
            border[0] + (size[0] + 2 * border[0]) * pos[0],
            border[1] + (size[1] + 2 * border[1]) * pos[1],
        )

    montage.paste(im1, box=box((0, 0)))
    montage.paste(compare, box=box((1, 0)))
    montage.paste(im2, box=box((2, 0)))

    return montage


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare two images")
    parser.add_argument("IMAGE1", type=Image.open)
    parser.add_argument("IMAGE2", type=Image.open)
    args = parser.parse_args(argv)

    out = diff(args.IMAGE1, args.IMAGE2)

    out.save(sys.stdout.buffer, format="PNG")


if __name__ == "__main__":
    main()
