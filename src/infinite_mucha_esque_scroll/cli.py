from pathlib import Path

import typer
from PIL import Image

from infinite_mucha_esque_scroll.logger import LogLevel, logger
from infinite_mucha_esque_scroll.out_painter import OutPainter

app = typer.Typer()

DEFAULT_PROMPT = """
a girl, (alphonse mucha), (art work), poster, art nouveau,
<lora:alphonseMucha_v12:0.6>,
a part of long vertical illustration,
monochrome,
<lora:animeLineartStyle_v20Offset:1.0>, line art,
""".strip()
DEFAULT_NEGATIVE_PROMPT = """
(low quality, worst quality:1.4), (bad anatomy),
(inaccurate limb:1.2),bad composition, inaccurate eyes,
extra digit,fewer digits,(extra arms:1.2), nude, nsfw,
""".strip()


def save_image_safely(img: Image.Image, path: Path, force: bool = False):
    if path.exists() and not force:
        logger.print(f"'{path}' already exists. Skipping.", style=LogLevel.WARNING)
        return

    img.save(path)
    logger.print(f"Successfully saved to '{path}'.", style=LogLevel.INFO)


@app.command()
def generate(
    # API
    server_url: str = typer.Option("http://127.0.0.1:7860", "-s", "--server-url"),
    # Input image
    previous_image: Path = typer.Option(None, "-i", "--previous-image"),
    overlap_height: int = typer.Option(200, "-l", "--overlap-height"),
    controlnet_model: str = typer.Option("canny", "--controlnet-model"),
    # New image
    height: int = typer.Option(800, "-H", "--height"),
    width: int = typer.Option(384, "-W", "--width"),
    seed: int = typer.Option(-1, "--seed"),
    prompt: str = typer.Option(DEFAULT_PROMPT, "-P", "--prompt"),
    negative_prompt: str = typer.Option(
        DEFAULT_NEGATIVE_PROMPT, "-N", "--negative-prompt"
    ),
    # Output file
    force_overwrite: bool = typer.Option(False, "-f", "--force-overwrite"),
    output_image: Path = typer.Option(
        None,
        "-o",
        "--output-image",
        help=(
            "The output path of the 'complete' image file. "
            "If 'previous_image' is supplied, you will get a concatenated image."
            "In other words, "
            "output_image = previous_image + output_overlap_image + output_new_image."
        ),
    ),
    output_overlap_image: Path = typer.Option(
        None,
        "-oO",
        "--output-overlap-image",
        help=(
            "The output path of the 'joint' image file. "
            "This image can be used to concat "
            "previous_image and the generated image (somehow) smoothly."
        ),
    ),
    output_new_image: Path = typer.Option(
        None,
        "-oN",
        "--output-new-image",
        help=(
            "The output path of the newly generated image file. "
            "This image is basically 'output_image' minus 'previous_image'."
        ),
    ),
    output_print_image: Path = typer.Option(
        None,
        "-oP",
        "--output-print-image",
        help=(
            "The output path of the image file for continuous printing. "
            "This image is basically `output_overlap_image` plus 'output_new_image' minus "
            "next `output_overlap_image`."
        ),
    ),
    debug: bool = typer.Option(
        False, "--debug", is_flag=True, help="Output intermediate images for debugging."
    ),
):
    """
    Generate a new image with/without a previous image
    """
    painter = OutPainter(server_url, debug=debug)

    if not previous_image:
        logger.print("Generating a new image.", style=LogLevel.INFO)

        img = painter.generate_new_image(
            guide_img=None,
            width=width,
            height=height,
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
        )
        if output_image:
            save_image_safely(img, output_image, force_overwrite)

        if output_overlap_image:
            logger.print(
                "Ignoring --output-overlap-image supplied.", style=LogLevel.WARNING
            )

        if output_new_image:
            save_image_safely(img, output_new_image, force_overwrite)

        if output_print_image:
            print_img = painter.generate_print_image(
                new_img=img, overlap_height=overlap_height
            )
            save_image_safely(print_img, output_print_image, force_overwrite)

        return

    logger.print(
        "Generating a new image based on the previous image.", style=LogLevel.INFO
    )
    prev_img = Image.open(previous_image)
    guide_img = painter.generate_guide_image(
        prev_img=prev_img,
        overlap_height=overlap_height,
        height=height,
    )
    new_img_with_overlap = painter.generate_new_image(
        guide_img=guide_img,
        width=width,
        height=guide_img.height,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        controlnet_model=controlnet_model,
    )
    concat_img, overlap_img = painter.concat_images_smoothly(
        prev_img=prev_img,
        new_img_with_overlap=new_img_with_overlap,
        overlap_height=overlap_height,
    )

    if output_image:
        save_image_safely(concat_img, output_image, force_overwrite)

    if output_overlap_image:
        save_image_safely(overlap_img, output_overlap_image, force_overwrite)

    if output_new_image:
        new_img = painter.remove_top_overlap_from_new_image(
            new_img=new_img_with_overlap, overlap_height=overlap_height
        )
        save_image_safely(new_img, output_new_image, force_overwrite)

    if output_print_image:
        print_img = painter.generate_print_image(
            new_img=new_img_with_overlap,
            overlap_height=overlap_height,
            smooth_overlap_img=overlap_img,
        )
        save_image_safely(print_img, output_print_image, force_overwrite)
