from typing import Optional
from urllib.parse import urlparse

import webuiapi
from PIL import Image, ImageDraw, ImageEnhance

from infinite_mucha_esque_scroll.logger import LogLevel, logger


class OutPainter:
    def __init__(self, server_url: str, debug: bool = False) -> None:
        self.client = self.create_client(server_url)
        self.debug = debug

    def create_client(self, url: str):
        parsed = urlparse(url)

        if parsed.hostname is None:
            raise Exception("Failed to get hostname.")
        if parsed.port is None:
            raise Exception("Failed to get port.")

        return webuiapi.WebUIApi(
            host=parsed.hostname, port=parsed.port, use_https=parsed.scheme == "https"
        )

    def generate_guide_image(
        self,
        prev_img: Image.Image,
        overlap_height: int,
        height: int,
    ):
        # Create a guide image
        # which is mainly blank but contains a part of the provided image
        guide_img = Image.new(
            "RGB", (prev_img.width, overlap_height + height), color="white"
        )
        # Clip a bottom part of the provided image
        prev_img_overlap_zone = (
            0,
            prev_img.height - overlap_height,
            prev_img.width,
            prev_img.height,
        )
        guide_img.paste(prev_img.crop(prev_img_overlap_zone))

        if self.debug:
            guide_img.save("debug.guide.png")

        return guide_img

    def generate_new_image(
        self,
        guide_img: Optional[Image.Image],
        width: int,
        height: int,
        prompt: str,
        negative_prompt: str,
        seed: int = -1,
        controlnet_model: str = "canny",
    ):
        cn_units = []

        if guide_img:
            cn = webuiapi.ControlNetInterface(self.client)
            model = next((x for x in cn.model_list() if controlnet_model in x), None)

            if not model:
                logger.print(cn.model_list(), style=LogLevel.INFO)
                raise Exception(f"ControlNet model '{controlnet_model}' not found.")

            logger.print(
                f"Using {model} as a ControlNet model.",
                style=LogLevel.INFO,
                markup=False,
            )

            cn_units.append(
                webuiapi.ControlNetUnit(
                    input_image=guide_img,  # type: ignore
                    module=controlnet_model,
                    model=model,
                    weight=1,
                    processor_res=512,
                    threshold_a=100,
                    threshold_b=200,
                )
            )

        with logger.status("Processing...", spinner="pong"):
            # Generate an image
            res = self.client.txt2img(
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                cfg_scale=7,
                steps=20,
                width=width,
                height=height,
                sampler_name="Euler a",
                controlnet_units=cn_units,
                use_deprecated_controlnet=True,
            )

        res_img = res.image

        if self.debug:
            res_img.save("debug.res.png")

        # Post processing
        res_img = ImageEnhance.Color(res_img).enhance(0)  # Convert to grayscale
        res_img = ImageEnhance.Contrast(res_img).enhance(3)  # Increase contrast

        return res_img

    def remove_top_overlap_from_new_image(
        self, new_img: Image.Image, overlap_height: int
    ):
        return new_img.crop((0, overlap_height, new_img.width, new_img.height))

    def remove_bottom_overlap_from_new_image(
        self, new_img: Image.Image, overlap_height: int
    ):
        return new_img.crop(
            (
                0,
                0,
                new_img.width,
                new_img.height - overlap_height,
            )
        )

    def remove_top_bottom_overlap_from_new_image(
        self, new_img: Image.Image, overlap_height: int
    ):
        return new_img.crop(
            (
                0,
                overlap_height,
                new_img.width,
                new_img.height - overlap_height,
            )
        )

    def generate_composite_mask_for_overlap(
        self, width: int, height: int, offset: float = 0.8
    ):
        """Generate white to black non-linear gradient mask for compositing"""
        mask_img = Image.new("L", (width, height), color="white")
        draw = ImageDraw.Draw(mask_img)

        for y in range(int(height * offset), height):
            fill = 255 - min(
                int(((y - height * offset) ** 1.5 / height) * 255),
                255,
            )
            draw.line(((0, y), (width, y)), fill=fill)

        if self.debug:
            mask_img.save("debug.mask.png")

        return mask_img

    def generate_smooth_overlap_image(
        self,
        prev_img: Image.Image,
        new_img_with_overlap: Image.Image,
        overlap_height: int,
    ):
        composite_mask_img = self.generate_composite_mask_for_overlap(
            prev_img.width, overlap_height
        )

        # Overlap position in each image
        prev_img_overlap_zone = (
            0,
            prev_img.height - overlap_height,
            prev_img.width,
            prev_img.height,
        )
        new_img_overlap_zone = (0, 0, prev_img.width, overlap_height)

        # Generate overlap image with compositing the images
        smooth_overlap_img = Image.composite(
            prev_img.crop(prev_img_overlap_zone),
            new_img_with_overlap.crop(new_img_overlap_zone),
            composite_mask_img,
        )

        if self.debug:
            smooth_overlap_img.save("debug.smooth_overlap_img.png")

        return smooth_overlap_img

    def concat_images_smoothly(
        self,
        prev_img: Image.Image,
        new_img_with_overlap: Image.Image,
        overlap_height: int,
    ):
        smooth_overlap_img = self.generate_smooth_overlap_image(
            prev_img, new_img_with_overlap, overlap_height
        )

        # Reserve new blank image and concat all the three images
        concat_img = Image.new(
            "RGB",
            (
                prev_img.width,
                prev_img.height + new_img_with_overlap.height - overlap_height,
            ),
        )
        concat_img.paste(prev_img, (0, 0))
        concat_img.paste(new_img_with_overlap, (0, prev_img.height - overlap_height))
        concat_img.paste(smooth_overlap_img, (0, prev_img.height - overlap_height))

        if self.debug:
            concat_img.save("debug.concat.png")

        return concat_img, smooth_overlap_img

    def generate_print_image(
        self,
        new_img: Image.Image,
        overlap_height: int,
        smooth_overlap_img: Optional[Image.Image] = None,
    ):
        print_img = self.remove_bottom_overlap_from_new_image(new_img, overlap_height)

        if smooth_overlap_img:
            print_img.paste(smooth_overlap_img, (0, 0))

        return print_img
